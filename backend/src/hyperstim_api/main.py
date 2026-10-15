"""FastAPI app. Run with: uvicorn --factory hyperstim_api.main:create_app"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from hyperstim_api.analysis import (
    Analyzer,
    Busy,
    ErrorCode,
    Pipeline,
    Record,
    ResearchPipeline,
    Status,
    TooManyRequests,
    estimate,
)
from hyperstim_api.config import Settings, load_settings
from hyperstim_api.dataset import Channel, Feature, Sort, Video, load_dataset

VIDEO_ID_PATTERN = r"^[A-Za-z0-9_-]{11}$"  # a YouTube video ID
VideoId = Annotated[str, Path(pattern=VIDEO_ID_PATTERN)]
CHANNEL_ID_PATTERN = r"^UC[A-Za-z0-9_-]{22}$"  # a YouTube channel ID
ChannelId = Annotated[str, Path(pattern=CHANNEL_ID_PATTERN)]


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Health(ApiModel):
    status: str


class Meta(ApiModel):
    video_count: int
    channel_count: int
    updated_at: str


class VideoSummary(ApiModel):
    id: str
    title: str
    channel_id: str
    channel: str
    score: float


class FeatureValue(ApiModel):
    key: str
    value: float | None
    percentile: float | None


class VideoDetail(VideoSummary):
    channel_in_dataset: bool  # false for a live video from a channel we don't have
    features: list[FeatureValue]


class ChannelSummary(ApiModel):
    id: str
    name: str
    score: float
    video_count: int


class ChannelVideo(ApiModel):
    id: str
    title: str
    published_at: str  # YYYY-MM-DD
    score: float
    features: list[FeatureValue]


class ChannelDetail(ApiModel):
    id: str
    name: str
    video_count: int
    score: float
    features: list[FeatureValue]  # mean raw value and mean percentile of its videos
    videos: list[ChannelVideo]  # oldest first


class VideoList(ApiModel):
    items: list[VideoSummary]
    total: int


class ChannelList(ApiModel):
    items: list[ChannelSummary]
    total: int


class Analysis(ApiModel):
    status: Status
    queue_position: int | None  # videos ahead, while queued
    progress: float  # 0-1, estimated
    remaining_s: int | None  # estimated seconds left
    error: ErrorCode | None


def feature_values(features: tuple[Feature, ...]) -> list[FeatureValue]:
    return [
        FeatureValue(
            key=f.key,
            value=f.value,
            percentile=None if f.percentile is None else round(f.percentile, 1),
        )
        for f in features
    ]


def video_detail(v: Video, channel_in_dataset: bool) -> VideoDetail:
    return VideoDetail(
        id=v.id,
        title=v.title,
        channel_id=v.channel_id,
        channel=v.channel,
        score=round(v.score, 1),
        channel_in_dataset=channel_in_dataset,
        features=feature_values(v.features),
    )


def channel_detail(c: Channel) -> ChannelDetail:
    return ChannelDetail(
        id=c.id,
        name=c.name,
        video_count=c.video_count,
        score=round(c.score, 1),
        features=feature_values(c.features),
        videos=[
            ChannelVideo(
                id=v.id,
                title=v.title,
                published_at=v.published_at or "",
                score=round(v.score, 1),
                features=feature_values(v.features),
            )
            for v in c.videos
        ],
    )


def analysis(record: Record, queue_position: int | None, now: float) -> Analysis:
    progress = estimate(record, now)
    return Analysis(
        status=record.status,
        queue_position=queue_position,
        progress=round(progress.share, 3),
        remaining_s=None if progress.remaining_s is None else round(progress.remaining_s),
        error=record.error,
    )


def create_app(settings: Settings | None = None, pipeline: Pipeline | None = None) -> FastAPI:
    """The app; `pipeline` replaces the research scripts in tests."""
    logging.basicConfig(level=logging.INFO)
    settings = settings or load_settings()
    dataset = load_dataset(settings.dataset_path)
    if pipeline is None:
        pipeline = ResearchPipeline(settings.ytdlp_cookies, settings.youtube_api_key)
        if settings.youtube_api_key is None:
            logging.getLogger(__name__).warning(
                "YOUTUBE_API_KEY is not set: live analysis accepts videos not made for kids"
            )
    analyzer = Analyzer(
        settings.analysis_dir,
        pipeline,
        settings.analysis_limit_per_ip,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        analyzer.start_worker()
        yield
        analyzer.stop_worker()

    app = FastAPI(title="HyperStim API", lifespan=lifespan)
    app.state.analyzer = analyzer
    app.add_middleware(
        CORSMiddleware, allow_origins=[settings.cors_origin], allow_methods=["GET", "POST"]
    )

    @app.get("/api/health")
    def health() -> Health:
        return Health(status="ok")

    @app.get("/api/meta")
    def meta() -> Meta:
        return Meta(
            video_count=len(dataset.videos),
            channel_count=dataset.channel_count,
            updated_at=dataset.updated_at,
        )

    @app.get("/api/videos")
    def videos(
        sort: Sort = "score_desc",
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> VideoList:
        items = [
            VideoSummary(
                id=v.id,
                title=v.title,
                channel_id=v.channel_id,
                channel=v.channel,
                score=round(v.score, 1),
            )
            for v in dataset.ranked_videos(sort, limit)
        ]
        return VideoList(items=items, total=len(dataset.videos))

    @app.get("/api/videos/{video_id}", responses={404: {"description": "Video not found"}})
    def video(video_id: VideoId) -> VideoDetail:
        """A dataset video, or one analyzed live (scored against the dataset)."""
        v = dataset.videos_by_id.get(video_id)
        if v is None:
            found = analyzer.snapshot(video_id)
            record = found[0] if found else None
            if record is not None and record.status == "done" and record.features is not None:
                v = dataset.score_video(
                    record.id,
                    record.title or record.id,
                    record.channel_id or "",
                    record.channel or "",
                    record.features,
                )
        if v is None:
            raise HTTPException(status_code=404, detail="Video not found")
        return video_detail(v, v.channel_id in dataset.channels_by_id)

    @app.post(
        "/api/analyses/{video_id}",
        status_code=202,
        responses={
            200: {"description": "Already done or running", "model": Analysis},
            429: {"description": "Too many new analyses from this IP address"},
            503: {"description": "The queue is full"},
        },
    )
    def start_analysis(video_id: VideoId, request: Request, response: Response) -> Analysis:
        """Start the live analysis of a video, or join it if it is stored or running."""
        if video_id in dataset.videos_by_id:
            response.status_code = 200
            return Analysis(
                status="done",
                queue_position=None,
                progress=1,
                remaining_s=None,
                error=None,
            )
        ip = request.client.host if request.client else ""
        try:
            _, created = analyzer.start(video_id, ip)
        except Busy:
            raise HTTPException(status_code=503, detail="Busy") from None
        except TooManyRequests:
            raise HTTPException(status_code=429, detail="Too many requests") from None
        if not created:
            response.status_code = 200
        found = analyzer.snapshot(video_id)
        assert found is not None  # just started or already there
        return analysis(*found, analyzer.clock())

    @app.get("/api/analyses/{video_id}", responses={404: {"description": "Never requested"}})
    def get_analysis(video_id: VideoId) -> Analysis:
        found = analyzer.snapshot(video_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return analysis(*found, analyzer.clock())

    @app.get("/api/channels")
    def channels(
        sort: Sort = "score_desc",
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        min_videos: Annotated[int, Query(alias="minVideos", ge=1, le=1000)] = 5,
    ) -> ChannelList:
        ranked, total = dataset.ranked_channels(sort, limit, min_videos)
        items = [
            ChannelSummary(id=c.id, name=c.name, score=round(c.score, 1), video_count=c.video_count)
            for c in ranked
        ]
        return ChannelList(items=items, total=total)

    @app.get("/api/channels/{channel_id}", responses={404: {"description": "Channel not found"}})
    def channel(channel_id: ChannelId) -> ChannelDetail:
        c = dataset.channels_by_id.get(channel_id)
        if c is None:
            raise HTTPException(status_code=404, detail="Channel not found")
        return channel_detail(c)

    return app
