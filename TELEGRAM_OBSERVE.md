# Telegram observation for a personal bot

Enable the opt-in mode in the Telegram channel configuration:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "allowFrom": ["YOUR_NUMERIC_TELEGRAM_USER_ID"],
      "observeGroupMessages": true
    }
  }
}
```

This mode applies to all groups and supergroups the bot joins, including new ones.
Only numeric IDs explicitly in `allowFrom` can trigger group turns. A Telegram
mention of the bot, including `/command@botname`, is required. Replying to the bot,
ordinary chatter, pairing approval, a wildcard, or `groupPolicy: open` cannot
bypass this requirement. Other members' mentions and commands are context only.
Owner inline-button clicks remain supported; other group members cannot use them.
Private-chat permissions and behavior retain their existing handling.

Recent text and captions from other members and untagged owners are retained in
`telegram-observed/` beside the active config file. Each group/topic has its own
atomic mode-600 snapshot, limited to 40 entries and approximately 12,000 characters
of serialized JSON. Individual messages are truncated to leave room for attachment
summaries. Attachments are recorded by type; observation never downloads,
transcribes, calls a model, runs tools, reacts, or sends typing/reply events.

When the owner tags the bot, recent context is added as attributed JSON explicitly
marked as untrusted conversation data before the current owner request. Existing
agent history is not rewritten. Context survives restart and remains isolated from
other groups, forum topics, and private chats. Observation starts when this mode
is enabled; historical Telegram messages are not fetched. Persistent snapshots can
be removed when the bot is stopped if the operator wants to forget that context.

Telegram must deliver ordinary group messages. In BotFather, use `/setprivacy`,
select the bot, and choose **Disable**; follow Telegram's re-add guidance for
existing groups. Alternatively, make the bot an admin in each intended group.
Privacy mode does not prevent explicit mentions, but it prevents passive
observation unless the bot has the required group privileges.

The Coolify template enables this mode. To roll it back, set
`observeGroupMessages` to `false` in the deployment template and redeploy through
Coolify. The previous code image and runtime data should be retained during rollout.
