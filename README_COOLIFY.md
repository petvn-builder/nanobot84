# Nanobot on Coolify

This guide deploys Nanobot as a Coolify Docker Compose resource. Coolify builds the image from this repository, renders `config.json` from Coolify environment variables at container startup, and exposes the WebUI/WebSocket service through your domain on port `8765`.

Secrets stay in Coolify environment variables. Do not commit real API keys or WebUI tokens.

## Create the Coolify Resource

1. In Coolify, create a new resource.
2. Choose **Docker Compose**.
3. Select your fork of `HKUDS/nanobot`.
4. Set the compose file path to `docker-compose.coolify.yml`.
5. Keep the build context as the repository root.
6. Add a domain to the `nanobot-gateway` service and route it to container port `8765`.

Port `8765` serves the WebUI and WebSocket channel. Port `18790` is Nanobot's gateway health/internal port and is exposed by Compose for validation, but your public domain should point at `8765`.

## Environment Variables

Add these variables in the Coolify resource:

```env
OPENROUTER_API_KEY=<your_openrouter_api_key>
NANOBOT_WEB_TOKEN=<choose_a_long_random_webui_token>
NANOBOT_MODEL=anthropic/claude-opus-4-6
```

`OPENROUTER_API_KEY` is written into the generated config at startup. `NANOBOT_WEB_TOKEN` protects the public WebUI/WebSocket endpoint. `NANOBOT_MODEL` sets the default OpenRouter model.

The rendered config is stored in the `nanobot_data` Docker volume at `/home/nanobot/.nanobot/config.json`, alongside workspace and runtime state.

## Deploy

1. Save the resource settings.
2. Save the environment variables.
3. Deploy from Coolify.
4. Watch the deployment logs for config rendering, gateway startup, and the WebSocket channel startup.
5. Open your configured domain. Enter `NANOBOT_WEB_TOKEN` when the WebUI asks for the token.

## Validate

From the VM, check the gateway health endpoint:

```bash
curl http://127.0.0.1:18790/health
```

Expected response:

```json
{"status": "ok"}
```

Check the public WebUI through your Coolify domain:

```bash
curl -I https://your-domain.example
```

You should receive an HTTP response from the Nanobot WebUI service. If the browser shows an auth form, use the value from `NANOBOT_WEB_TOKEN`.

## Troubleshooting

**Container exits before gateway startup**

Check Coolify logs. The config renderer fails fast when `OPENROUTER_API_KEY`, `NANOBOT_WEB_TOKEN`, or `NANOBOT_MODEL` is unset or empty.

**WebUI loads but login fails**

Confirm the token entered in the browser exactly matches `NANOBOT_WEB_TOKEN`. Redeploy after changing the value in Coolify.

**Domain shows a bad gateway or blank page**

Confirm Coolify routes the domain to service `nanobot-gateway` on container port `8765`, not `18790`.

**Health check fails**

Check logs for provider/config errors. The health endpoint is `http://127.0.0.1:18790/health` inside the VM/container network.

**Sandbox or bwrap errors**

The compose file includes Nanobot's documented bwrap settings: `cap_drop: ALL`, `cap_add: SYS_ADMIN`, `apparmor=unconfined`, and `seccomp=unconfined`. If Coolify or the host blocks these settings, commands using the bwrap sandbox may fail with permission errors.

**Config changes do not appear**

The startup renderer overwrites `/home/nanobot/.nanobot/config.json` on each container start from `config.template.json` and Coolify environment variables. Update environment variables in Coolify, then redeploy or restart the service.
