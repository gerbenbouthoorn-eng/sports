# Picnic dinner helper

Plans a week of dinners and puts the groceries in your Picnic cart, using the
community [mcp-picnic](https://github.com/ivo-toby/mcp-picnic) MCP server
(configured in `.mcp.json`). It is not an official Picnic product.

## One-time setup

1. **Add your Picnic login as environment variables.** Never put them in a file
   in this repo.
   - `PICNIC_USERNAME`: your Picnic e-mail address
   - `PICNIC_PASSWORD`: your Picnic password
   - `PICNIC_COUNTRY_CODE` (optional): `NL` (default), `DE` or `FR`

   In a Claude Code cloud session, add them in the environment settings (the
   cloud environment menu in the session's title bar, then Edit). On your own
   computer, `export` them in your shell before starting `claude`.

2. **Allow network access to Picnic** (cloud sessions only): add
   `*.picnicinternational.com` to the environment's allowed domains.

3. **Start a new session** in this repo. Claude Code asks once whether to trust
   the `picnic` server in `.mcp.json`; approve it. Run `/mcp` to check that it
   shows as connected.

4. **Two-factor login**: if Picnic asks for a code, tell Claude "log in to
   Picnic". It sends you an SMS code, and you give that code to Claude.

## Example requests

- "Plan 5 dinners for 2 people this week, budget €60, no fish."
- "Show me quick Picnic recipes and add the ingredients for 3 of them to my cart."
- "What's in my cart now and what does it cost?"
- "Which delivery slots are available on Thursday?"

Claude fills the cart, but you check out and pay in the Picnic app yourself.
