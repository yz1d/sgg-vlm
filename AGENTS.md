Generals:
- No backward compatibility. Break old formats freely. Don't keep any old code or data which will only interfere with your future refactoring.
- When I say "sgg-vlm.bak", I mean source code in `_references/sgg-vlm.bak`. Never write or change it. Treat it as a reference or inspiration critically.
- We are using jj/jujustsu instead of git.

Techology & Toolings:
- Modern Python toolings around uv.

Scope:
- We will only focus on front camera image frame for now.
- Scene graph generation will only work on single frame. The only temporal processing we might we is tracking association for an object across frame.