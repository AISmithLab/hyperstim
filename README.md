<p align="center">
  <a href="https://aismithlab.com/hyperstim/">
    <img src=".github/readme/banner.png" width="900" alt="HyperStim? How stimulating are the videos your child watches?">
  </a>
</p>

<p align="center">
  <a href="https://aismithlab.com/hyperstim/"><b>Website</b></a> &nbsp;|&nbsp;
  <a href="https://aismithlab.com/hyperstim/how-it-works/">How it works</a> &nbsp;|&nbsp;
  <a href="https://aismithlab.com/hyperstim/rankings/">Rankings</a> &nbsp;|&nbsp;
  <a href="https://aismithlab.com/hyperstim/compare/">Compare</a>
</p>

<p align="center">
  <a href="https://sonarcloud.io/summary/new_code?id=AISmithLab_hyperstim"><img src="https://sonarcloud.io/api/project_badges/measure?project=AISmithLab_hyperstim&metric=alert_status" alt="Quality gate status"></a>
  <a href="https://sonarcloud.io/summary/new_code?id=AISmithLab_hyperstim"><img src="https://sonarcloud.io/api/project_badges/measure?project=AISmithLab_hyperstim&metric=coverage" alt="Coverage"></a>
  <a href="https://github.com/AISmithLab/hyperstim/actions/workflows/deploy.yml"><img src="https://github.com/AISmithLab/hyperstim/actions/workflows/deploy.yml/badge.svg" alt="Deploy status"></a>
</p>

## About

HyperStim? helps parents see how stimulating children's YouTube videos are. It measures a video's production style (how fast the scenes change, how bright and colorful the picture is, how loud the sound is) and turns it into a score you can compare across videos and channels.

## Features

- **Check a video:** paste a YouTube link and get its score.
- **Rankings:** the most and least stimulating videos and channels.
- **Compare:** two videos or two channels side by side.

## A growing dataset

We add videos and channels every day. The chart is redrawn daily from the dataset's [changelog](backend/data/collected/CHANGELOG.tsv).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="backend/data/collected/growth-dark.svg">
  <img src="backend/data/collected/growth.svg" alt="Line chart of the number of videos and channels in the HyperStim dataset over time, redrawn daily.">
</picture>

## Development

A static Next.js site on GitHub Pages and a Python (FastAPI) API that serves the dataset and analyzes new videos. See [`DEVELOPMENT.md`](DEVELOPMENT.md) to run it locally or contribute.

## License

[Apache 2.0](LICENSE)
