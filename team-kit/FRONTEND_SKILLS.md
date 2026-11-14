# Frontend agent skills — installed November 14, 2026

Generic tooling, installed user-level (`-g`) on this PC for Kiro CLI, Codex and
Antigravity. These are instruction packs for agents, not project code or runtime
libraries; runtime packages (three, gsap, motion...) are installed inside
`frontend/` during the event from the committed lockfile.

Locations: `~/.kiro/skills/` (Kiro) and `~/.agents/skills/` (Codex, Antigravity).
60 skills. Source clones with pinned commits: `~/skill-staging/`.

| Source repo @ commit | License | Skills installed |
|---|---|---|
| anthropics/skills @2c5958e | Apache-2.0 (per skill) | frontend-design, webapp-testing |
| vercel-labs/agent-skills @1a2c79d | none at repo root, check per skill | web-design-guidelines, vercel-react-best-practices |
| microsoft/playwright-cli @ce9b41b | Apache-2.0 | playwright-cli |
| EnzeD/r3f-skills @4a11805 | none at repo root | all 11 r3f-* |
| CloudAI-X/threejs-skills @0e18186 | MIT | all 13 threejs-* |
| greensock/gsap-skills @aed9cfd | MIT | all 8 gsap-* |
| discover-dmc/motionstack @fe95c1d | MIT | motion-framer, rive-interactive, lottie-animations, blender-web-pipeline, spline-interactive, web3d-integration-patterns, modern-web-design, animejs, react-spring-physics |
| Star-957/vrm-avatar-polish-loop @10be79a | MIT | vrm-avatar-polish-loop, review-loop |
| remotion-dev/skills @1af7e69 | none at repo root | remotion-best-practices |
| pbakaus/impeccable @f866ce1 | Apache-2.0 | impeccable |
| kylezantos/design-motion-principles @4a9ca87 | MIT | design-motion-principles |
| delphi-ai/animate-skill @71bc617 | none found | animate |
| arjun988/blender-skills @904f095 | MIT | export-pipeline, asset-optimization, lod-pipeline, lowpoly-style, materials, lighting, camera-cinematography, qa-review |

## Not installed, and why

- **oso95/scroll-world**: builds the page from paid AI-generated video clips
  (Higgsfield / Monid, pay-per-clip). Adds cost, an external account and
  synthetic imagery that could be mistaken for satellite observations. Reuse its
  idea only if wanted: a vanilla-JS scroll scrubber over a pre-rendered video.
- **blender-director** (blender-skills): its SKILL.md has a YAML error (duplicate
  key) and the CLI rejected it. The other 180 blender-skills are game-art styles
  and genres, irrelevant to this project.
- **scroll-reveal-libraries** (motionstack): YAML error, CLI rejected it.
- **Remaining remotion-* skills, and anthropics/vercel extras**: not needed.
- **awwwards.com/websites/3d** and the two Instagram reels: visual references, not
  skills. Use them as mood references for P3 only.

## Notes and cautions

- `impeccable` downloads a helper binary from its GitHub releases on first run
  (`scripts/impeccable.cmd` on Windows). Allow it or let the skill fall back to
  reading PRODUCT.md / DESIGN.md directly.
- Skills run with the agent's full permissions. Scanned for curl|sh, iex, key
  exfiltration and similar patterns before installing; nothing found. That is a
  pattern scan, not a security audit.
- Repos without a root license grant no reuse rights for their example code.
  Use them as guidance; do not copy examples into the submission.
- Plan rule still applies: Story/3D/motion are P2. Calendar, evidence and the
  static judge site come first; no animation may invent data between observations.

## Reproduce on a teammate PC

```powershell
npx -y skills@latest add <owner>/<repo> -g -a kiro-cli codex antigravity --copy -y -s <skill> [<skill> ...]
```

Use the skill names from the table. Pin to the listed commits by cloning the repo,
`git checkout <commit>`, and passing the local path instead of `<owner>/<repo>`.
