"""FastAPI app. Run with: uvicorn --factory hyperstim_api.main:create_app"""

import logging
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from hyperstim_api.config import Settings, load_settings
from hyperstim_api.dataset import Sort, load_dataset


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


class ChannelSummary(ApiModel):
    id: str
    name: str
    score: float
    video_count: int


class VideoList(ApiModel):
    items: list[VideoSummary]
    total: int


class ChannelList(ApiModel):
    items: list[ChannelSummary]
    total: int


def create_app(settings: Settings | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    settings = settings or load_settings()
    dataset = load_dataset(settings.dataset_path)

    app = FastAPI(title="HyperStim API")
    app.add_middleware(CORSMiddleware, allow_origins=[settings.cors_origin], allow_methods=["GET"])

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

    return app
