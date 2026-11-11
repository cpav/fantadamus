# Set up Fantadamus on your Mac

Fantadamus tells you who to field in Fantacalcio, inside your own Claude Desktop. It reads the round's lineups and
odds and every player's season figures itself, and Claude reads the few other pages it needs from a short list of
approved sites; Fantadamus checks every fact, stores it on your Mac and does the arithmetic. This guide takes about
15 minutes.

**You need:** a Mac, [Claude Desktop](https://claude.ai/download) signed in to a Claude plan with web search,
and the Terminal app (in Applications → Utilities). Windows isn't supported yet.

**What it does:** for the next round, the full lineup for your squad under your league's rules: the eleven, the
bench in order and the formation, with the expected score and the chance of reaching each goal threshold. It also
answers "X or Y?" between two players of the same role, gives one player's outlook ("Will he start? Is he worth
it?"), shows a match on one screen or the whole round at a glance, and after a round reviews the lineup you fielded.

## 1. Install uv

uv runs Fantadamus with the right Python version. In Terminal, run:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then quit Terminal (⌘Q) and open it again, so it finds `uv`.

## 2. Get the code

```bash
git clone https://github.com/cpav/fantadamus.git ~/fantadamus
```

If your Mac offers to install "command line developer tools", accept, wait for it to finish, and run the
command again.

## 3. Check that it runs

```bash
cd ~/fantadamus && uv run --frozen --no-dev fantadamus --help
```

The first run downloads what it needs (a minute or so), then prints the command `serve`.

## 4. Note two paths

```bash
which uv
```

```bash
echo ~/fantadamus
```

You'll paste both into Claude Desktop's settings: typically `/Users/YOU/.local/bin/uv` and
`/Users/YOU/fantadamus`, where `YOU` is your Mac user name.

## 5. Add Fantadamus to Claude Desktop

1. Quit Claude Desktop (⌘Q).
2. Open its settings file. If it doesn't exist yet, this creates it:

   ```bash
   mkdir -p ~/Library/Application\ Support/Claude && touch ~/Library/Application\ Support/Claude/claude_desktop_config.json && open -a TextEdit ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

3. If the file is empty, paste this, replacing `YOU` with your Mac user name (both places) and `your-name`
   with a short lower-case name for yourself (letters, digits or `-`), for example `marco`:

   ```json
   {
     "mcpServers": {
       "fantadamus": {
         "command": "/Users/YOU/.local/bin/uv",
         "args": ["--directory", "/Users/YOU/fantadamus", "run", "--frozen", "--no-dev", "fantadamus", "serve", "--user", "your-name"]
       }
     }
   }
   ```

   If the file already has content, keep it and add the `"mcpServers": { … }` part as one more entry at the
   top level, separated from its neighbour by a comma. If it already has an `"mcpServers"` section, add only
   the `"fantadamus": { … }` entry inside it.

4. Save, then check the file. This prints it back, or names the line with a mistake:

   ```bash
   python3 -m json.tool ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

5. Open Claude Desktop. In **Settings → Developer**, `fantadamus` should show as running.

## 6. Create a Fantadamus project

A project with Fantadamus's instructions makes Claude use the tools without being asked every time.

1. In Claude Desktop, open **Projects** and create one called **Fantadamus**.
2. Open the agent prompt, either at
   [`docs/agent-prompt.md` on GitHub](https://github.com/cpav/fantadamus/blob/main/docs/agent-prompt.md) or in
   `~/fantadamus/docs/agent-prompt.md`. Copy everything **below the `---` line**.
3. Paste it into the project's **instructions**.
4. Optional, and it saves typing: fill in your league profile. Copy
   [`docs/league-profile-template.md`](https://github.com/cpav/fantadamus/blob/main/docs/league-profile-template.md),
   fill it in and paste it **below the agent prompt**, in the same instructions. It holds your league's rules, your
   squad and how you like to play. Leave out what you don't know: Claude will ask. Keep your filled-in copy to
   yourself, because it holds your league's team names and rosters.
5. Save. In a chat in that project, open the tools menu under the message box and make sure **web search** and
   **fantadamus** are both on.

## 7. Ask your first question

In a new chat in the Fantadamus project, ask for example:

> Who do I field this round?

- **The first time**, Claude needs your league's rules and your squad. With a league profile, it saves them itself.
  Without one, it asks: bonuses and maluses, offering the Classic values (goal +3, assist +1, yellow −0.5, and so
  on), then the goal thresholds, the bench, substitutions and allowed formations, any modifiers and the captain,
  and your players. You can change any of it later by asking.
- **Or paste your league's rulebook.** Claude turns it into Fantadamus's rules, then reads back what's priced and
  what's left out: check that it understood. A rule Fantadamus can't price yet, such as the home factor, is saved
  by name, and every answer says its score leaves it out. What a rule can be is in
  [`docs/league-rules.md`](https://github.com/cpav/fantadamus/blob/main/docs/league-rules.md).
- Claude Desktop asks permission before each Fantadamus tool. "Allow always" is fine: everything runs on
  your Mac.
- Claude then reads the pages Fantadamus lists (lineups, odds, players' profiles, the table), submits what
  they say and asks again. The first answer can take a few minutes; later ones reuse what's stored.
- The answer starts with the formation, the expected score and the chance of each threshold, then the eleven, the
  bench in order, the calls that matter and what to check before the deadline.
- If you'd rather play someone else, say so. Claude says once what that costs, then helps with your choice.

You can also ask "Lautaro or Thuram this round?", "Which formation?", "How do I order my bench?" or "Will Lautaro
start?". For a match, ask "Tell me about Inter–Como": its card gives the odds as plain chances, the goals and clean
sheets, both likely elevens and how sure they are, who's out, the penalty takers, the likeliest scorers and your
players in it, first. For the whole round, ask "Where are the goals this round?" or "Which keepers are safest?".

If Claude answers without showing a Fantadamus tool block, say "Use Fantadamus for this".

## 8. Keep the forecast fresh (optional)

Your Mac can check the round's lineups and odds in the background, so answers are already fresh when you
ask, even minutes before the deadline. Every 15 minutes it looks at what's due, and reads Fantacalcio-Online's
round page only if something is: lineups twice a day from three days before a match, every 3 hours on the
last day; odds daily, then every 3 hours; official lineups every 15 minutes in the 75 minutes before
kickoff. Once a day it also reads Fantacalcio.it's statistics page, with every player's season figures, and its penalty-takers
page.
Nothing runs while your Mac sleeps.

Paste this whole block into Terminal. It writes the schedule with your own paths:

```bash
mkdir -p ~/Library/LaunchAgents ~/fantadamus/data/local/collect
cat > ~/Library/LaunchAgents/com.github.cpav.fantadamus.collect.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.github.cpav.fantadamus.collect</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(which uv)</string>
    <string>--directory</string>
    <string>$HOME/fantadamus</string>
    <string>run</string>
    <string>--frozen</string>
    <string>--no-dev</string>
    <string>fantadamus</string>
    <string>collect</string>
    <string>--due</string>
  </array>
  <key>StartInterval</key>
  <integer>900</integer>
  <key>StandardOutPath</key>
  <string>$HOME/fantadamus/data/local/collect/schedule.log</string>
  <key>StandardErrorPath</key>
  <string>$HOME/fantadamus/data/local/collect/schedule.log</string>
</dict>
</plist>
EOF
```

Then switch it on:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.github.cpav.fantadamus.collect.plist
```

To see what it did, run `cd ~/fantadamus && uv run --frozen --no-dev fantadamus collect --report`: the last
run, and when the page last worked. To switch it off:

```bash
launchctl bootout gui/$(id -u)/com.github.cpav.fantadamus.collect
```

## After a round: your review

About 12 hours after a round's last match, ask:

> How did my round 11 go?

Claude asks what you fielded (the eleven, the bench in order, the captain and vice) or whether you followed the advice,
and your total from your league's app. Fantadamus works out your real score from the statistics page the way your
league scores it, and puts your app's total beside it. Then each choice you made against the advice: what it was
expected to cost when you made it, and what it really did. A choice is judged by the first, because one round is
mostly luck. Over the season it keeps a record of whether your overrides pay off, and says when it's too early to
tell. What you fielded and your reviews stay on your Mac.

## How it checks itself

There's nothing to do here. About 12 hours after a round's last match, at your next question or scheduled run,
Fantadamus reads who really started and scores the chances it gave. Your next lineup says how that went, in one line.
To see the whole report:

```bash
cd ~/fantadamus && uv run --frozen --no-dev fantadamus calibrate --round 11
```

## Keeping it up to date

```bash
cd ~/fantadamus && git pull
```

Then quit and reopen Claude Desktop. If `docs/agent-prompt.md` has changed, copy it again as in step 6 and paste it
again over the old one in the project's instructions, keeping your league profile below it.

## If something goes wrong

- **Claude says a fact is still missing right after submitting it:** ask again a minute later.
- **`fantadamus` shows an error in Settings → Developer:** the log is in
  `~/Library/Logs/Claude/mcp-server-fantadamus.log`. Send the last lines to whoever shared this guide.
- **The schedule (step 8) seems idle:** its output is in `~/fantadamus/data/local/collect/schedule.log`;
  "Nothing due." is normal between reads.
- **Starting over:** your league rules, your squads, the stored facts, the log of answers and the scores are in
  `~/fantadamus/data/local/`. Quitting Claude Desktop and deleting that folder resets everything.

Your data stays on your Mac. For now each player collects their own facts; a shared online version comes
later.
