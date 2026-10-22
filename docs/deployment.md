# Deployment

`.github/workflows/deploy.yml` runs on every pull request and push:

1. **test**: `ruff check`, `ruff format --check`, `pytest` against a Postgres service container, then `alembic upgrade head` + `alembic check`.
2. **deploy** (only `main`, on push or manual run; uses the `development` environment):
   check configuration → build the image → push to Artifact Registry (tag = commit SHA) → deploy the Cloud Run service
   → smoke test `GET /health/ready`.

The application runs `alembic upgrade head` on startup (`RUN_MIGRATIONS_ON_STARTUP`, default `true`). A revision whose
migration fails never becomes ready, so Cloud Run keeps serving the previous revision.

GitHub authenticates to Google Cloud with a service account JSON key stored in the `GCP_CREDENTIALS` secret.
The same service account deploys and runs the service. The database is any external PostgreSQL (for example Neon);
its URL comes from the `DATABASE_URL` secret and is passed to Cloud Run as an environment variable.

## Database URL

Paste the connection string exactly as the provider gives it, for example Neon:

```
postgresql://USER:PASSWORD@ep-xxx-pooler.c-2.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

`Settings` converts it for asyncpg: the scheme becomes `postgresql+asyncpg`, `sslmode` becomes `ssl` and
`channel_binding` (not supported by asyncpg) is dropped.

## One-time Google Cloud setup

Replace the placeholders and run once.

```bash
PROJECT_ID=dev-project-study
FIREBASE_PROJECT_ID=project-study-dev-8d5b5
REGION=southamerica-east1
REPO=api

gcloud services enable run.googleapis.com artifactregistry.googleapis.com --project $PROJECT_ID
gcloud artifacts repositories create $REPO --repository-format=docker --location=$REGION --project $PROJECT_ID
```

### Service account and key

```bash
gcloud iam service-accounts create deployment-github --project $PROJECT_ID
SA=deployment-github@$PROJECT_ID.iam.gserviceaccount.com

for role in roles/run.admin roles/artifactregistry.writer; do
  gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$SA --role=$role
done
gcloud iam service-accounts add-iam-policy-binding $SA \
  --member=serviceAccount:$SA --role=roles/iam.serviceAccountUser --project $PROJECT_ID

gcloud iam service-accounts keys create gcp-credentials.json --iam-account=$SA --project $PROJECT_ID
```

Paste the content of `gcp-credentials.json` into the GitHub secret `GCP_CREDENTIALS`, then delete the local file.
The key does not expire: if it leaks, delete it with `gcloud iam service-accounts keys delete KEY_ID --iam-account=$SA`
and create a new one. If key creation fails with `iam.disableServiceAccountKeyCreation`, an organization policy admin
can lift it: `gcloud resource-manager org-policies disable-enforce iam.disableServiceAccountKeyCreation --project $PROJECT_ID`.

### Firebase in a separate project

The API manages users' custom claims, so the service account needs Firebase Authentication Admin in the Firebase project
(it can be a different project from Cloud Run):

```bash
gcloud projects add-iam-policy-binding $FIREBASE_PROJECT_ID --member=serviceAccount:$SA --role=roles/firebaseauth.admin
gcloud services enable identitytoolkit.googleapis.com --project $FIREBASE_PROJECT_ID
```

If calls fail with "Identity Toolkit API has not been used in project …", enable `identitytoolkit.googleapis.com` in the
project named in the error as well.

### Image bucket (optional)

Without `GCS_BUCKET_NAME` the API runs normally and image uploads answer 503. When you create the bucket:

```bash
BUCKET=project-study-images
gcloud storage buckets create gs://$BUCKET --location=$REGION --uniform-bucket-level-access --project $PROJECT_ID
gcloud storage buckets add-iam-policy-binding gs://$BUCKET --member=allUsers --role=roles/storage.objectViewer
gcloud storage buckets add-iam-policy-binding gs://$BUCKET --member=serviceAccount:$SA --role=roles/storage.objectAdmin
```

Then add the `GCS_BUCKET_NAME` variable and redeploy.

## GitHub configuration

Everything lives in the `development` environment (Settings → Environments → development).

**Environment secrets**

| Secret | Value |
| --- | --- |
| `GCP_CREDENTIALS` | Full content of `gcp-credentials.json` |
| `DATABASE_URL` | PostgreSQL connection string (Neon format accepted as is) |
| `REDIS_URL` | Optional Redis URL for the response cache (`rediss://default:<password>@<host>:6379` on Upstash); missing disables caching |

**Environment variables, required** (the deploy fails early listing any missing one)

| Variable | Example |
| --- | --- |
| `GCP_PROJECT_ID` | `dev-project-study` |
| `GCP_REGION` | `southamerica-east1` |
| `GAR_REPOSITORY` | `api` |
| `CLOUD_RUN_SERVICE` | `project-study-api` |
| `GCP_SERVICE_ACCOUNT` | `deployment-github@dev-project-study.iam.gserviceaccount.com` |
| `FIREBASE_PROJECT_ID` | `project-study-dev-8d5b5` |

**Environment variables, optional** (missing ones use the default; empty ones are not sent)

| Variable | Default | Effect when missing |
| --- | --- | --- |
| `GCS_BUCKET_NAME` | none | Image uploads return 503; image `url` is `null` |
| `INVITE_BASE_URL` | none | Invites return `url: null`; the client builds the link from `token` |
| `APP_NAME` | `project-study-api` | |
| `API_V1_PREFIX` | `/api/v1` | |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `5` / `5` | |
| `DB_ECHO` | `false` | |
| `RUN_MIGRATIONS_ON_STARTUP` | `true` | |
| `IMAGE_MAX_BYTES` | `5242880` | |
| `STUDY_TIMEZONE` | `America/Sao_Paulo` | |
| `CACHE_TTL_SECONDS` | `600` | Upper bound for cached responses (also capped by token and invite expiry) |

Do not set `PORT` or `K_REVISION`: Cloud Run injects them (each revision gets a fresh cache namespace).

The service is deployed with `--allow-unauthenticated` because authentication happens in the API with Firebase ID tokens.
