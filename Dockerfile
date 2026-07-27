##
# Ivrit.ai Crowd Recital Server Build
# Author: Yoad Snapir
#
# This Dockerfile build the production docker container.
# It has two main stages:
# - Building the static web client (using Vite)
# - Installing the FastAPI web server that serves both the API endpoints
#   and the static web app at the root
##

##
# Build the Vite app static site
##

FROM --platform=$BUILDPLATFORM node:20-slim AS build-stage
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

RUN pnpm run build

# At this point, static files are built into the /app/dist folder

##
# Start the production container build
##

# Python base image - use xhost's exact warm-base tag (python:3.11-slim) so those
# base layers are exempt from the platform's charged image-size cap.
FROM python:3.11-slim AS final-stage

# FFMPEG is needed for the audio processing
RUN apt-get -y update && apt-get -y upgrade && apt-get install -y --no-install-recommends ffmpeg

WORKDIR /server
COPY server/requirements.txt .
# Pre install torch using offical pytorch wheel - to match target platform
# RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir "torch<=2.3.0" --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Download and store the stanza models into the image
# Setup an env that also tells stanza where to download/look for modes
# during runtime
WORKDIR /
ENV STANZA_RESOURCES_DIR=stanza_resources
RUN python -c "import stanza; stanza.download('he', processors='tokenize,mwt')"

# Copy the backend code
WORKDIR /server
COPY server/ .

WORKDIR /

# Copy the built static assets from the build-stage
COPY --from=build-stage /app/dist web_client_dist/

# Specify the volume where uploaded data is to be stored
VOLUME /data

EXPOSE 80

# Run DB migrations (needs cwd=/server, see alembic.ini prepend_sys_path=.)
# then start uvicorn from the root folder, binding to the platform-injected
# $PORT when present (falls back to 80 for local `docker run` usage per the README).
ENTRYPOINT [ "sh", "-c", "cd /server && alembic upgrade head && cd / && exec uvicorn --app-dir=server application:app --host 0.0.0.0 --port ${PORT:-80}" ]