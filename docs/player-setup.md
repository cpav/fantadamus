# Set up Fantadamus on your Mac

Fantadamus answers "X or Y?" for two Serie A forwards, inside your own Claude Desktop. Claude collects the
facts from a short list of approved sites; Fantadamus checks them, stores them on your Mac and does the
arithmetic. This guide takes about 15 minutes.

**You need:** a Mac, [Claude Desktop](https://claude.ai/download) signed in to a Claude plan with web search,
and the Terminal app (in Applications → Utilities). Windows isn't supported yet.

**What it does for now:** "X or Y?" between two forwards for the next round. Keepers, defenders,
midfielders, full lineups and formations come in later versions.

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
3. Paste it into the project's **instructions** and save.
4. In a chat in that project, open the tools menu under the message box and make sure **web search** and
   **fantadamus** are both on.

## 7. Ask your first question

In a new chat in the Fantadamus project, ask for example:

> Lautaro or Thuram this round?

- **The first time**, Claude asks for your league's bonuses and maluses, offering the Classic values (goal
  +3, assist +1, yellow −0.5, and so on). Give your league's values; you can change them later by asking.
- Claude Desktop asks permission before each Fantadamus tool. "Allow always" is fine: everything runs on
  your Mac.
- Claude then reads the pages Fantadamus lists (lineups, odds, players' profiles, the table), submits what
  they say and asks again. The first answer can take a few minutes; later ones reuse what's stored.
- The answer starts with the verdict ("start X, put Y first on the bench"), then the margin, the reasons
  and what to check before the deadline.

If Claude answers without showing a Fantadamus tool block, say "Use Fantadamus for this".

## Keeping it up to date

```bash
cd ~/fantadamus && git pull
```

Then quit and reopen Claude Desktop.

## If something goes wrong

- **Claude says a fact is still missing right after submitting it:** ask again a minute later.
- **`fantadamus` shows an error in Settings → Developer:** the log is in
  `~/Library/Logs/Claude/mcp-server-fantadamus.log`. Send the last lines to whoever shared this guide.
- **Starting over:** your league rules, the stored facts and the log of answers are in
  `~/fantadamus/data/local/`. Quitting Claude Desktop and deleting that folder resets everything.

Your data stays on your Mac. For now each player collects their own facts; a shared online version comes
later.
