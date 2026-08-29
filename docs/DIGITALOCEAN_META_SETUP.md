# DigitalOcean production host and Meta WhatsApp setup

## 1. Create the DigitalOcean host

Open the [DigitalOcean Control Panel](https://cloud.digitalocean.com/) and create
one Droplet with:

- region: Frankfurt,
- image: Ubuntu 24.04 LTS,
- plan: Basic / Regular, 1 vCPU, 2 GiB RAM, 50 GiB SSD,
- authentication: SSH key, no password,
- hostname: `sovereign-01`,
- monitoring enabled,
- daily DigitalOcean backups enabled,
- Advanced Options / User Data: paste `deploy/digitalocean/cloud-init.yaml`.

The 2 GiB Basic Droplet is currently USD 12/month. Daily backups are 30% of the
Droplet price, so the host and provider backup together are about USD 15.60/month
before model and WhatsApp usage.

Cloud-init installs Docker, Compose, UFW, fail2ban and unattended security
updates. It admits only SSH, HTTP and HTTPS and creates the SSH user `deploy`.

## 2. DNS and HTTPS

Create a DNS `A` record such as:

`agent.example.com -> DROPLET_IPV4`

Copy the project to `/opt/sovereign`, then:

```bash
cp .env.sovereign.example .env.sovereign
cp .env.digitalocean.example .env.digitalocean
```

Set `AGENT_DOMAIN` to the DNS name and `ACME_EMAIL` to an operational email.
Caddy obtains and renews the public certificate automatically. Only `/webhook`
and `/healthz` are exposed; port 8080 never reaches the public host interface.

Fill `.env.sovereign` only on the Droplet and run:

```bash
bash deploy/digitalocean/deploy.sh
curl https://agent.example.com/healthz
```

The organism and backup process share one named volume. The backup process uses
SQLite's online backup API every six hours, verifies each copy and retains 28
recovery points. DigitalOcean's daily Droplet backup is the second recovery
layer.

## 3. Create or select the Meta Business Portfolio

1. Open [Meta Business Suite](https://business.facebook.com/).
2. Sign in with the Facebook account that will administrate the company.
3. Create a Business Portfolio if none exists, or select the correct existing
   company portfolio.
4. Record the Business Portfolio ID from Business Settings / Business Info.

Use a company-owned portfolio, enable two-factor authentication for all admins
and add a second trusted administrator. Do not create the production assets in
an employee's disposable personal portfolio.

## 4. Create the Meta developer app

1. Open [Meta for Developers / My Apps](https://developers.facebook.com/apps/).
2. Choose **Create App**.
3. Select the WhatsApp use case when offered.
4. Connect the same Business Portfolio.
5. In the App Dashboard open **WhatsApp -> Quickstart** or **API Setup**.

Meta changes labels occasionally, but the required objects remain one Meta app,
one connected Business Portfolio, one WhatsApp Business Account and one Cloud
API phone number.

## 5. Register the eSIM number

When the eSIM is active:

1. Add its telephone number in WhatsApp API Setup.
2. Receive the SMS or voice verification code on the eSIM.
3. Submit the display name for approval.
4. Copy the generated **Phone Number ID**. This is not the telephone number.

Keep the new number unused in consumer WhatsApp until Cloud API registration is
complete. The roles are deliberately different:

- eSIM number: the organism's WhatsApp Business sender,
- `OWNER_WA_ID`: Roberto's existing personal WhatsApp number, the primary
  admitted sender,
- `WHATSAPP_ALLOWED_WA_IDS`: optional comma-separated additional people who may
  converse with the organism,
- `WHATSAPP_PHONE_NUMBER_ID`: Meta's generated numeric asset ID for the eSIM.

## 6. Collect the four Meta values

Put these directly into `.env.sovereign` on the Droplet:

| Environment variable | Meta location |
| --- | --- |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp / API Setup |
| `WHATSAPP_ACCESS_TOKEN` | temporary token in API Setup for testing; later a permanent System User token |
| `META_APP_SECRET` | App Settings / Basic / App Secret |
| `META_VERIFY_TOKEN` | a long random value chosen by us, identical on server and webhook setup |

For production, create a System User in Business Settings, assign the app and
WhatsApp assets, and generate a token with the minimum required WhatsApp
messaging/management permissions. Never paste tokens into chat, source code or
the Docker image.

## 7. Connect the webhook

In the app's WhatsApp webhook configuration:

- callback URL: `https://AGENT_DOMAIN/webhook`
- verify token: the exact value of `META_VERIFY_TOKEN`
- subscribed field: `messages`

Meta first performs a GET challenge. Afterwards signed POST events enter the
durable queue. The host rejects wrong signatures, other business phone IDs and
every sender except `OWNER_WA_ID` and the explicitly configured
`WHATSAPP_ALLOWED_WA_IDS`.

## 8. Production transition

The test token is temporary. Before leaving test mode:

- finish business verification if Meta requests it,
- use the System User token,
- switch the app to Live when eligible,
- approve any proactive message templates,
- test inbound text, intentional silence and one outbound reply,
- export and restore one SQLite recovery point before long-running operation.
