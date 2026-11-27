# Namespace Decision

Load this for any finding with `action=new` on an area that lives under a
namespaced tree (`skill` or `steering`). retro MUST ask the user where the new
artefact belongs before writing files, because inferring the namespace from the
finding's content puts files where the user won't look.

Aliases `LIST_NS` and `CHECK_TARGET` are declared in SKILL.md `## Commands`.

1. Enumerate installed namespaces:

   ```bash
   $LIST_NS
   ```

2. Show the list and ask: "Where should this <area> live? (e.g. `home` for
   a home-flat entry, `aws/util` for a categorised aws entry)". STOP and
   wait for the user.

3. Check the answer as `{location}`:

   ```bash
   $CHECK_TARGET --check --area <skill|steering> \
       --location <location> --name <name>
   ```

   Pass: exit 0, stdout is the path to write. Fail: exit 1 with the reason
   on stderr (missing directory, malformed name, or target already exists);
   show the reason and re-prompt from sub-step 2.

4. Write the new artefact only at the path the check printed.
