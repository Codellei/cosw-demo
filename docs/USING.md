# Use the Remotish demo

**Demo:** https://codellei.github.io/cosw-demo/ (available after Pages publication).

1. Open the link in a desktop browser. Code OSS Web launches with **Dark+**,
   **Remotish**, and **Remotish GitHub Provider** already included.
2. A fresh browser session starts with an **empty editor**. Select **File → Open Folder**
   to choose a browser-supported local folder, where the browser permits it.
   A previously opened workspace may be restored on later visits. If the old
   `Hello-World` folder still appears, choose **File → Close Folder** once to
   return to the empty workspace; the demo does not discard your browser state.
3. To open **a public GitHub repository through Remotish**, use this address format:

   ```text
   https://codellei.github.io/cosw-demo/?repo=OWNER/REPOSITORY
   ```

   For example: [Open Codellei/remotish](https://codellei.github.io/cosw-demo/?repo=Codellei/remotish).

After opening a repository, use **Explorer** to browse files and **Source Control**
to inspect local changes. The standard Open Folder picker does not necessarily
browse remote GitHub repositories; use the `?repo=` link above for those.

The link accepts only ordinary GitHub owner/repository names. It takes
precedence over your previously selected workspace and is removed from
the browser address after it has been accepted. Keep or share the **original
link with `?repo=`** as your bookmark.

## What can you do?

Browse public repository files and history, switch among existing branches,
and try local edits, staging and diffs. The browser may preserve your local
working overlay for later visits.

**No GitHub account or token is needed.** This demo cannot open private
repositories, push commits, create remote branches or change the remote
repository. Edits are **local to your browser**, not saved to GitHub.

## If something doesn't open

- Confirm that the repository is **public** and `OWNER/REPOSITORY` is correct.
- GitHub can limit anonymous API requests. Try again later if rate-limited.
- Try a current desktop Chromium/Chrome/Edge browser. Browser storage,
  company network policies, CORS and local data permissions can affect behavior.
- Browser storage is scoped to the demo's site; clearing site data can erase
  local editor state. Don't put secrets into this public demonstration.

For issues, include your browser and the public repository you tried in
[the issue tracker](https://github.com/Codellei/cosw-demo/issues);
**never include tokens, private source or personal data**.
