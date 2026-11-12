# rr-ndas

RocketRush NDA generator. **Read `SYSTEM.md` before doing anything.** It defines the chat workflow:

- User says "Hey" → list the NDAs from `ndas.json`, then offer "new".
- User says "new" → ask the six questions one at a time, confirm, run `python3 scripts/generate.py`,
  run the tests, commit, push, and reply with the NDA link.
- Rocket Rush is always the Receiving Party. Never edit clause wording in `template.html` without being asked.
