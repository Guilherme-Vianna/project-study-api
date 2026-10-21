# Deployment

`.github/workflows/deploy.yml` runs on every pull request and push:

1. **test**: `ruff check`, `ruff format --check`, `pytest` against a Postgres service container, then `alembic upgrade head` + `alembic check`.
2. **deploy** (only `main`, on push or manual run; uses the `production` environment):
   build the image → push to Artifact Registry (tag = commit SHA) → run migrations as the Cloud Run Job
   `<service>-migrate` → deploy the Cloud Run service → smoke test `GET /health/ready`.

GitHub authenticates to Google Cloud with a service account JSON key stored in the `GCP_CREDENTIALS` secret.
The same service account deploys and runs the service.

## One-time Google Cloud setup

Replace the placeholders and run once.

```bash
PROJECT_ID=my-project
REGION=southamerica-east1
REPO=api
BUCKET=project-study-images
SQL_INSTANCE=$PROJECT_ID:$REGION:study-db

gcloud services enable run.googleapis.com artifactregistry.googleapis.com sqladmin.googleapis.com \
  secretmanager.googleapis.com identitytoolkit.googleapis.com --project $PROJECT_ID

gcloud artifacts repositories create $REPO --repository-format=docker --location=$REGION --project $PROJECT_ID
```

### Service account and key

```bash
gcloud iam service-accounts create study-api --project $PROJECT_ID
SA=study-api@$PROJECT_ID.iam.gserviceaccount.com

for role in roles/run.admin roles/artifactregistry.writer roles/cloudsql.client \
  roles/secretmanager.secretAccessor roles/firebaseauth.admin; do
  gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$SA --role=$role
done
gcloud iam service-accounts add-iam-policy-binding $SA \
  --member=serviceAccount:$SA --role=roles/iam.serviceAccountUser --project $PROJECT_ID

gcloud iam service-accounts keys create gcp-credentials.json --iam-account=$SA --project $PROJECT_ID
```

Paste the content of `gcp-credentials.json` into the GitHub secret `GCP_CREDENTIALS`, then delete the local file.
The key does not expire: if it leaks, delete it with `gcloud iam service-accounts keys delete KEY_ID --iam-account=$SA`
and create a new one.

If key creation fails with `iam.disableServiceAccountKeyCreation`, an organization policy blocks keys. An organization
policy admin can lift it for this project:

```bash
gcloud resource-manager org-policies disable-enforce iam.disableServiceAccountKeyCreation --project $PROJECT_ID
```

### Database URL secret

```bash
printf 'postgresql+asyncpg://USER:PASSWORD@/DB?host=/cloudsql/%s' "$SQL_INSTANCE" | \
  gcloud secrets create database-url --data-file=- --project $PROJECT_ID
```

### Image bucket

```bash
gcloud storage buckets create gs://$BUCKET --location=$REGION --uniform-bucket-level-access --project $PROJECT_ID
gcloud storage buckets add-iam-policy-binding gs://$BUCKET --member=allUsers --role=roles/storage.objectViewer
gcloud storage buckets add-iam-policy-binding gs://$BUCKET --member=serviceAccount:$SA --role=roles/storage.objectAdmin
```

## GitHub configuration

Create the `production` environment (Settings → Environments; add required reviewers if you want manual approval).

**Secret** (Settings → Secrets and variables → Actions → Secrets):

| Secret | Value |
| --- | --- |
| `GCP_CREDENTIALS` | Full content of `gcp-credentials.json` |

**Variables** (Settings → Secrets and variables → Actions → Variables):

| Variable | Example |
| --- | --- |
| `GCP_PROJECT_ID` | `my-project` |
| `GCP_REGION` | `southamerica-east1` |
| `GAR_REPOSITORY` | `api` |
| `CLOUD_RUN_SERVICE` | `project-study-api` |
| `CLOUD_SQL_INSTANCE` | `my-project:southamerica-east1:study-db` |
| `DATABASE_URL_SECRET` | `database-url` |
| `GCP_SERVICE_ACCOUNT` | `study-api@my-project.iam.gserviceaccount.com` |
| `FIREBASE_PROJECT_ID` | `my-project` |
| `GCS_BUCKET_NAME` | `project-study-images` |
| `INVITE_BASE_URL` | `https://app.example.com/invites` |

The service is deployed with `--allow-unauthenticated` because authentication happens in the API with Firebase ID tokens.
