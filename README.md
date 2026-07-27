# crowd-recital
Crowd-sourced Text Recital Acquisition

# Table of Contents

1. [Deployment](#deployment)
   - [Prerequisites](#prerequisites)
   - [Setup](#setup)
   - [ID Delegation Authentication](#id-delegation-authentication)
   - [Analytics](#analytics)
   - [DB Migration](#db-migration)
   - [Running the Server - No Docker Option](#running-the-server---no-docker-option)
   - [Running the Background Jobs (Optional)](#running-the-background-jobs-optional)
   - [Running the Server - Docker Option](#running-the-server---docker-option)
   - [Using a Reverse Proxy (like nginx)](#using-a-reverse-proxy-like-nginx)

2. [Operations](#operations)
   - [Speaker Users](#speaker-users)

3. [Development](#development)
   - [Prerequisites](#prerequisites-1)
   - [The Vite Development Web Server](#the-vite-development-web-server)
   - [The FastAPI Web Server](#the-fastapi-web-server)

4. [Bump Versions](#bump-versions)

## Deployment

### Prerequisites

- Python >= 3.10 and < 3.12 Installed
- Docker (To build the web client static site)
- ffmpeg available on the path of the running python process (For transcoding)
- AWS bucket to upload content and keys for the principal which can upload objects to that bucket

### Setup

- Clone this repo
- Inside the `/server` directory
- Create a virtual environment and install the requirements
`python -m venv ./venv`
`pip install -r requirements.txt`

- Create a `.env` file in the `/server` directory and add the following variables

```
DB_CONNECTION_STR=<PostgreSQL Connection String>
GOOGLE_CLIENT_ID=<Google client id for the Google login app>
ACCESS_TOKEN_SECRET_KEY=<Generated secret to sign the JWT session tokens>
DELEGATED_IDENTITY_SECRET_KEY=<Secret key to for id delegation authentication (See Below)>
AWS_ACCESS_KEY_ID=<AWS access key>
AWS_SECRET_ACCESS_KEY=<AWS secret access key>
AWS_DEFAULT_REGION=<The region for the S3 bucket access>
CONTENT_STORAGE_S3_BUCKET=<AWS S3 bucket name for the uploaded content>
CONTENT_DISABLE_S3_UPLOAD=<True/False - Disable content uploading - for development purposes (False)>
JOB_SESSION_FINALIZATION_DISABLED=<True/False - enable or disable aggregations+upload jobs (True)>
JOB_SESSION_FINALIZATION_INTERVAL_SEC=<Seconds between runs of aggregation+upload jobs, read more below. (120)>
PUBLIC_POSTHOG_KEY=<optional - tracking to posthog>
PUBLIC_POSTHOG_HOST=<optional - tracking to posthog>
DEBUG=<True/False - prints db and other detailed logs (False)>
EMAIL_SENDER_ADDRESS=<email to send from>
DEV_AUTO_LOGIN_USER_EMAIL=<optional - for development only - automatically login with this user email>
```

*JOB_SESSION_FINALIZATION_INTERVAL_SEC*: Note, the server will also immediately trigger finalization when a recording session ends when this flag is turned on to minimize latency of getting an available session preview.

- Back on the root folder
- If going with the "No Docker" deployment option - build the web client static assets yourself (requires Node.js + pnpm, see `web_client/package.json` for the pinned `packageManager` version) and place the output in a `web_client_dist` folder at the repo root:

```
cd web_client
pnpm install --frozen-lockfile
pnpm run build --outDir ../web_client_dist
```

- If you run the web server with a non root user (good idea) make sure the created dist folder is owned by that user.

`sudo chown -R <user>:<group> web_client_dist`

- If you further intend on serving static files from the proxy - make sure the proxy has read/list access to that folder

- If going with the Docker deployment option - see below.

### ID Delegation Authentication

Trusted system who needs to access the API on behalf of another user will use a method which is not a normal OAuth flow for simplicity.

In that method, the delegating system (For this project, this is a Retool admin app) will send this secret key (Which you can randomly generate just like `ACCESS_TOKEN_SECRET_KEY`) and the email of the user it asks to operate on behalf of.
The two are sent with each API call on the following two headers respectively:

- `x-delegation-secret-key`
- `x-delegated-user-email`

*Note:* This is not a very strong method, but it works. Fore reference, the way to implement this is to have an identity provider that would implement an OAuth flow that would provide Retool with the credentials to work on behalf of the user.
Retool (for example) supports OAuth 2.0 authentication, it's just the implementation of the IDp on the Python server that is currently missing.
Btw, An external service provider (Like Auth0 could be used, but might cost something)

### Analytics

This project can integrate with a [PostHog](https://posthog.com/) project got analytics.
Set the proper env vars to enable this integration.

### DB Migration

If this is not the first deployment - migrate the DB in case schema changes were made.

*note:* Ensure the python venv is active before running the following.

```sh
cd server
alembic upgrade head
```

### Running the server - No Docker option
- Starting the server using uvicorn (Default port is 8000) (Make sure the virtual environment is activated)

`uvicorn --app-dir=server application:app`

Assuming you have a reverse proxy in from of the server for HTTPS/caching/static file serving - also add the following to the uvicorn command:

`--forwarded-allow-ips='*' --proxy-headers`

If you have your reverse proxy forward to a Unix Domain socket you will also add something like this:

`--uds /tmp/uvicorn.recital.sock`

**Note:** The uvicorn command runs from the root folder NOT the `server` folder.

### Running the background jobs (Optional)

*note:* Ensure the python venv is active before running the following.

The server will automatically execute those jobs for you unless disabled using the proper ENV var. If disabled you can externally schedule those jobs as described below.

- Schedule a job to execute the following admin scripts:

`python server/admin_client.py aggregate_sessions`

This will aggregate "ended" sessions or "active" sessions that are too old into "vtt" and "audio" files.

It will also transcode the audio into a "main" audio format (the best quality data) and "light" audio format (suitable for web playback).

This script deletes the audio segment files and replaces them with a single "raw source" audio file which is also kept.

- Schedule a job to upload the artifacts of the session to AWS S3

`python server/admin_client.py upload_sessions`

This script uploads text and audio artifacts into the S3 bucket under a "folder" prefix named after the session id.

Each such folder will contain a vtt file and 3 audio files (source, main and light).

### Running the server - Docker option

- Build the Docker image `Dockerfile` (The default)
- Ensure you are on the root folder

`docker build -t crowd-recital .`

- Command to run the server docker image

`docker run -p 8000:80 --env-file server/.env docker.io/library/crowd-recital:latest`

This binds the web server on the host port 8000.

- You would probably want this container to auto start when stopped so add `--restart unless-stopped` to the above command.

- Note that this server does not handle HTTPS - so a proxy (like nginx) is expected in front of it. In that case you will add to the docker run command also the following:

`--forwarded-allow-ips='*' --proxy-headers`

So that the internal container run uvicorn will be able to see the access request headers.

- Don't forget to make sure your proxy also auto starts if it's installed on the host.

### Using a reverse proxy (like nginx)

The web app uses local client routing.

The server should respond to any path which does NOT start with `/api` or `/env` with the `index.html` file at the `web_client_dist/assets` folder.

The assets folder is served from the python web server root in case you do not want to serve the static files directly from the reverse proxy server.

Regardless - consider a setup something like this (nginx in this case) to respect the client side routing:

```
  location ~ ^/(api|env) {
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_redirect off;
    proxy_buffering off;
    proxy_pass http://uvicorn;
  }

  location /assets {
    # path for static files
    root /path/to/app/web_client_dist;
  }

  location / {
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_redirect off;
    proxy_buffering off;
    proxy_pass http://uvicorn/;
    rewrite ^.*$ / break;
  }
```
(This goes under the "server" block in the nginx site config)

This configuration will ensure the app is always served on those paths, and the client JS will take over and render the routes as expected.

## Operations

### Speaker Users

Only "speaker" and "admin" users can use the recital web UI.

To approve (or pre approve if the user did not sign up yet) a speaker user - obtain their email address. Then run:

*note:* Ensure the python venv is active before running the following.

`python server/admin_client.py approve_speaker --speaker-email their@email.com`

from the root folder.

*note*: A simple Retool app to manage users and sessions was created to simplify the above. We look into how this can be properly shared or replace it with a built-in admin abilities.

## Development

### Development Auto-Login

For easier local development, you can use the `DEV_AUTO_LOGIN_USER_EMAIL` environment variable to automatically log in as a specific user without going through the Google authentication flow. This is particularly useful for testing and development purposes.

To use this feature:

1. Add `DEV_AUTO_LOGIN_USER_EMAIL=your-email@example.com` to your `.env` file
2. Ensure the email corresponds to a user that already exists in the database
3. When the server starts, any unauthenticated requests will automatically be authenticated as this user

#### Creating Development Users

To create development users for testing, you can run the following SQL script against your PostgreSQL database. This script creates two users: one with "speaker" permissions and one with "admin" permissions.

```sql
-- Create a speaker user
INSERT INTO users (
    id, 
    email, 
    email_verified, 
    name, 
    picture, 
    "group", 
    created_at, 
    updated_at
) VALUES (
    gen_random_uuid(), -- Generate a random UUID
    'speaker@example.com', -- Replace with your desired email
    TRUE, -- Email verified
    'Test Speaker', -- User's name
    'https://example.com/avatar.png', -- Optional profile picture URL
    'speaker', -- User group: 'speaker' or 'admin'
    CURRENT_TIMESTAMP, -- Created timestamp
    CURRENT_TIMESTAMP -- Updated timestamp
);

-- Create an admin user
INSERT INTO users (
    id, 
    email, 
    email_verified, 
    name, 
    picture, 
    "group", 
    created_at, 
    updated_at
) VALUES (
    gen_random_uuid(), -- Generate a random UUID
    'admin@example.com', -- Replace with your desired email
    TRUE, -- Email verified
    'Test Admin', -- User's name
    'https://example.com/avatar.png', -- Optional profile picture URL
    'admin', -- User group: 'admin' for full administrative access
    CURRENT_TIMESTAMP, -- Created timestamp
    CURRENT_TIMESTAMP -- Updated timestamp
);
```

After running this script, you can set `DEV_AUTO_LOGIN_USER_EMAIL=speaker@example.com` or `DEV_AUTO_LOGIN_USER_EMAIL=admin@example.com` in your `.env` file to automatically log in as either user.

**Important Notes:**
- The `group` field determines the user's permissions:
  - `speaker`: Can use the recital web UI to record audio
  - `admin`: Has full administrative access to the system
- This feature should only be used in development environments
- A console warning will be displayed when this feature is active
- The auto-login only happens when no other authentication method is present

### Prerequisites

- Python >= 3.11 and < 3.12 Installed
- Node 20 available on PATH
- Install tbump with `pipx install tbump`
- add `.env` file inside the `/server` folder with these environment variables
```
DB_CONNECTION_STR=<PostgreSQL Connection String>
GOOGLE_CLIENT_ID=<Google client id for the Google login app>
ACCESS_TOKEN_SECRET_KEY=<Generated secret to sign the JWT session tokens>
DELEGATED_IDENTITY_SECRET_KEY=<Secret key to for id delegation authentication (See Below)>
AWS_ACCESS_KEY_ID=<AWS access key>
AWS_SECRET_ACCESS_KEY=<AWS secret access key>
AWS_DEFAULT_REGION=<The region for the S3 bucket access>
CONTENT_STORAGE_S3_BUCKET=<AWS S3 bucket name for the uploaded content>
CONTENT_DISABLE_S3_UPLOAD=<True/False - Disable content uploading - for development purposes (False)>
JOB_SESSION_FINALIZATION_DISABLED=<True/False - enable or disable aggregations+upload jobs (True)>
JOB_SESSION_FINALIZATION_INTERVAL_SEC=<Seconds between runs of aggregation+upload jobs, read more below. (120)>
PUBLIC_POSTHOG_KEY=<optional - tracking to posthog>
PUBLIC_POSTHOG_HOST=<optional - tracking to posthog>
DEBUG=<True/False - prints db and other detailed logs (False)>
EMAIL_SENDER_ADDRESS=<email to send from>
DEV_AUTO_LOGIN_USER_EMAIL=<optional - for development only - automatically login with this user email>
```

GOOGLE_CLIENT_ID & ACCESS_TOKEN_SECRET_KEY - instructions can be found here: https://support.google.com/cloud/answer/15549257?hl=en# 

You need to start two web servers from two shells.

### The Vite development web server
- Go into "web_client" and run:
1. `pnpm install`
2. `pnpm run dev`

### The FastAPI web server

- Make sure the virtual environment is activated
- Create a `cert` folder under the root
- Generate self signed certificates using the following command (from the root)

`openssl req -x509 -newkey rsa:4096 -keyout cert/key.pem -out cert/cert.pem -days 365 -nodes`

- From the server folder:
1. Create venv `python -m venv ./venv` (Don't forget to activate the venv)
2. install the requirements: `pip install -r requirements.txt`

- From the root folder:
1. Create a web_client_dist folder 
2. run uvicorn using the certificates in the `cert` folder
`uvicorn --app-dir=server application:app --reload --ssl-keyfile ./cert/key.pem --ssl-certfile ./cert/cert.pem`

- Access the app on `https://localhost:5173`

## Bump versions

Use tbump from the "server" folder:

`tbump 4.3.2`
