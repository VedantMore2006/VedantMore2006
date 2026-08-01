# Manual steps to finish the profile

Everything below needs your GitHub/Vercel account directly — I can't do these for you.

## 1. Push everything to `main`
The banner (`assets/build/svg/dark.svg`, `light.svg`), the workflow
(`.github/workflows/snake.yml`), and the new `README.md` all need to be committed and
pushed so `raw.githubusercontent.com` links resolve.

## 2. Self-host the stats cards (~20 min)
The README currently points at the **public** github-readme-stats instance, which
rate-limits constantly ("API rate limit exceeded"). To fix:
1. GitHub → Settings → Developer settings → Tokens (classic) → Generate new (classic),
   scope `repo`, no expiration. Copy it immediately, never paste it anywhere public.
2. Fork `github.com/anuraghazra/github-readme-stats`.
3. vercel.com → sign up with GitHub → Hobby (free) → Add New Project → import your fork.
4. Environment Variables → add `PAT_1` = your token → Deploy.
5. Copy your instance URL (`your-instance.vercel.app`).
6. In `README.md`, replace `github-readme-stats.vercel.app` with your instance URL in
   both stats-card `<img src>` lines.

## 3. Turn on the contribution snake
1. This repo's Settings (not your account settings) → Actions → General → scroll to
   **Workflow permissions** → select **Read and write permissions** → Save.
2. Push to `main` (or Actions tab → "Generate Snake Animation" → Run workflow).
3. Wait for the run to go green (~1 min) — this creates the `output` branch.
4. In `README.md`, uncomment the "Contribution Snake" `<picture>` block (currently
   wrapped in `<!-- -->`).

## 4. Verify theme switching
GitHub avatar → Settings → Appearance → toggle theme → reload your profile page.
Both `dark.svg` and `light.svg` should render correctly, and the animation should play
(intro shimmer, then the portrait/Python/OpenCV/Ultralytics loop).

## 5. Clean up scratch files
Once you're happy with the result, these can be deleted — they were exploration/rejects
kept around only for comparison:
- `assets/source/DSC_2816.jpg` (rejected — busy background)
- `assets/source/this.png` (rejected — first background-removal pass)
- `preview_portrait_*.png/svg` if still present anywhere (early GrabCut-based attempt)

Keep: `assets/source/background removed.png` (final source photo),
`assets/build/pipeline.py`, `travelers.py`, `animate.py`, `chrome.py` (regenerate
everything from source if you ever want to tweak it), and `assets/build/svg/dark.svg`
+ `light.svg` (what the README actually links to).
