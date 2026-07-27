##
# Ivrit.ai Crowd Recital Server Build
# Author: Yoad Snapir
#
# This Dockerfile builds a container that is has whats
# needed to build the static web app
# When run it build the Vite web app into a specified
# mounted volume on the host
##

##
# Build the Vite app static site
##

FROM node:20-slim AS build-stage
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
# Pin pnpm explicitly to match web_client/package.json's "packageManager" field -
# newer Corepack defaults can otherwise auto-fetch a pnpm release that requires a
# newer Node than this base image ships, breaking the build.
RUN corepack enable && corepack prepare pnpm@9.6.0 --activate

WORKDIR /app
COPY ./web_client .


# Cache the build deps for pnpm - subsequent builds should be faster
RUN --mount=type=cache,target=${PNPM_HOME}/store \
    pnpm config set store-dir ${PNPM_HOME}/store && \
    pnpm install --frozen-lockfile --prefer-offline

ENTRYPOINT [ "pnpm", "run", "build", "--", "--outDir", "dist" ]