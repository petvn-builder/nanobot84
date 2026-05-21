# Coolify Deployment

This deployment keeps Nanobot private, Telegram-only, and managed by Coolify. It builds from the official repository Dockerfile, starts `nanobot gateway`, stores runtime data in a Docker volume, and does not publish the WebUI or API publicly.

## Coolify Resource

Create a new Coolify resource:

- Project: `nanobot`
- Environment: `production`
- Resource type: `Docker Compose`
- Repository: `HKUDS/nanobot` or your fork
- Compose file: `docker-compose.coolify.yml`
- Build context: repository root

Do not add a public domain for the first deployment. Telegram uses outbound polling, so the container does not need a public HTTP endpoint.

## Environment Variables

Add these in Coolify under the resource's Environment Variables:

```env
TELEGRAM_TOKEN=your_botfather_token
TELEGRAM_ALLOW_FROM=your_telegram_user_id
NANOBOT_WEB_TOKEN=long_random_websocket_token
NANOBOT_PROVIDER=9router
NANOBOT_9ROUTER_BASE_URL=https://9router.pvn.world/v1
NANOBOT_9ROUTER_API_KEY=your_9router_dashboard_key
NANOBOT_9ROUTER_MODEL=your_9router_model_id
```

Secrets stay in Coolify. Do not put real API keys or Telegram tokens in Git.

`NANOBOT_PROVIDER=9router` is accepted by Nanobot and mapped internally to the `nine_router` provider field. 9Router should hold your Claude Code, Codex/OpenAI, and other upstream account credentials; Nanobot only needs the 9Router API key and model ID.

## 9Router Validation

Run these from the VM after filling the key and model ID in your shell or Coolify secret preview:

```bash
export NANOBOT_9ROUTER_BASE_URL=https://9router.pvn.world/v1
export NANOBOT_9ROUTER_API_KEY=your_9router_dashboard_key
export NANOBOT_9ROUTER_MODEL=your_9router_model_id

curl -fsS "$NANOBOT_9ROUTER_BASE_URL/models" \
  -H "Authorization: Bearer $NANOBOT_9ROUTER_API_KEY"

curl -fsS "$NANOBOT_9ROUTER_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $NANOBOT_9ROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$NANOBOT_9ROUTER_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with nanobot-9router-ok\"}],\"max_tokens\":32}"
```

An unauthenticated `/models` request should return `401`; that still confirms DNS and TLS reachability.

## Telegram Setup

Create the bot:

1. In Telegram, open `@BotFather`.
2. Send `/newbot`.
3. Follow the prompts.
4. Copy the token into Coolify as `TELEGRAM_TOKEN`.

Get your Telegram user ID:

1. Send a message to `@userinfobot`, or another trusted Telegram ID helper bot.
2. Copy your numeric user ID.
3. Set `TELEGRAM_ALLOW_FROM` to that exact ID.

Only the ID in `TELEGRAM_ALLOW_FROM` is allowed to use this bot. Do not set it to `*`.

## Deploy

1. In Coolify, save the resource settings.
2. Add the environment variables.
3. Deploy the resource.
4. Open the deployment logs in Coolify.
5. Look for the gateway startup messages and Telegram channel startup.

The Compose file includes a container health check against `http://127.0.0.1:18790/health`. This endpoint is checked inside the container and is not published publicly.

## Test

1. Open Telegram.
2. Start a private chat with your bot.
3. Send `/start` or a short message like `hello`.
4. Confirm Nanobot replies.

If the bot does not reply, check Coolify logs first. Common causes are an incorrect `TELEGRAM_TOKEN`, an incorrect `TELEGRAM_ALLOW_FROM`, or a missing provider API key for the selected `NANOBOT_PROVIDER`.

For a local CLI smoke test with Docker Compose:

```bash
docker compose run --rm nanobot-cli agent -m "Reply with nanobot-9router-ok"
```

For a coding execution smoke test, keep the sample repo inside Nanobot's workspace:

```bash
docker compose run --rm nanobot-cli agent \
  -w /home/nanobot/.nanobot/workspace/sample-repo \
  -m "Run pwd and git status, then report the current branch."
```

Shell execution is disabled in the checked-in production config. To enable repo-level shell commands intentionally, set `tools.exec.enable` to `true` in the rendered Nanobot config or a private deployment override, keep `tools.restrictToWorkspace=true`, and keep `tools.exec.sandbox=bwrap`.

Claude Code and Codex CLI execution should be authenticated outside Nanobot. In Docker, either bake the CLIs into a private image or mount a trusted CLI installation into the container and expose its directory with `tools.exec.pathAppend`. Do not put Claude, Codex, or OpenAI secrets in Nanobot config; connect those accounts in 9Router or through each CLI's own secure login storage.

## Updates

To update Nanobot:

1. Pull the latest changes into your fork or keep the Coolify resource pointed at the upstream branch you trust.
2. Redeploy the resource in Coolify.
3. Watch logs after deployment.
4. Test the Telegram bot again.

To roll back, use Coolify's deployment history and redeploy the previous working deployment.

## Security Notes

- Keep deployment managed by Coolify only.
- Do not run Nanobot separately with systemd or PM2.
- Do not expose the API or WebUI publicly yet.
- Do not add a public domain until you intentionally enable and secure an HTTP-facing interface.
- Keep `NANOBOT_9ROUTER_API_KEY` only in Coolify secrets or process environment variables.
- Keep `tools.exec.enable` set to `false` until you explicitly decide to allow shell commands.
- When shell commands are enabled, keep `tools.restrictToWorkspace=true` and `tools.exec.sandbox=bwrap`.
- Keep coding workspaces under `/home/nanobot/.nanobot/workspace`.
- Tool call names and statuses are logged by Nanobot; do not log raw tool arguments that may contain secrets.
- Keep `TELEGRAM_ALLOW_FROM` restricted to your Telegram user ID.
- Keep secrets in Coolify environment variables, not in repository files.

## Rollback

1. In Coolify, redeploy the previous working deployment from deployment history.
2. If rolling back manually, restore the previous `config.coolify.json`, `docker-compose.coolify.yml`, and environment variable set.
3. Remove `NANOBOT_9ROUTER_*` variables only after the old provider variables are restored.
4. Restart the Nanobot container and test Telegram or `nanobot agent` again.

## Extending Later

Future integrations can be added by editing `config.coolify.json` and adding matching Coolify environment variables. Good next steps are Gmail, Calendar, n8n webhooks, MCP servers with explicit `enabledTools`, file summary, and image generation. Enable one integration at a time and redeploy through Coolify after each change.
