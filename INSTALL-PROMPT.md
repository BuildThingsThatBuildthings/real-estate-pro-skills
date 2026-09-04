# Give this prompt to your AI agent

Copy the prompt below. It installs the starter skills when your AI supports installation, then helps configure your business context and the connections you choose. Some AI apps need you to upload a skill or finish an account sign-in yourself. The agent must verify each step instead of promising automatic installation everywhere.

<!-- PROMPT_START -->
Help me install and set up AI Acceleration for my real estate business inside the AI agent I am using now.

Use the official repository: https://github.com/BuildThingsThatBuildthings/real-estate-pro-skills
Read INSTALL-PROMPT.md, starter/manifest.json and the starter skill instructions from that repository, or from the official starter package I attach. The four starter skills are My Context Card, Content, Listing Machine and Listing Photos. Use the existing repository; do not invent a replacement product or install unrelated plugins. If a file is unavailable, say exactly what is missing and continue with the supplied package. Do not invent its contents.

Speak plainly. Ask one or two related questions at a time, reuse answers I already gave, and let me skip anything I do not know. Complete useful setup work between questions. Do not make me fill out a long technical questionnaire.

1. CHECK THIS AI ENVIRONMENT AND INSTALL THE SKILLS
Identify which AI app or agent I am using and what installation, filesystem and connector tools are actually available. If you can install skills, inspect the repository's starter installer and run its dry-run first, using this workspace by default. Show conflicts rather than overwriting existing skills or instructions. Install only the four starter skills, then read them back and verify their names and version. If you cannot install skills yourself, guide me through the supported upload/setup flow using the packaged skill ZIPs. If this environment can only use attached instructions in the current conversation, explain that limit and use them here without claiming persistent installation. Do not ask me to change AI providers. MCP is not required for v1.

2. UNDERSTAND MY BUSINESS AND REUSE MY CONTEXT
Ask my name, business or brokerage, role, market, audience and the work I most want help with. Ask whether I already have custom instructions, context cards, brand/voice files or useful examples. Reuse only the files I select. Resolve contradictions with me. Build or improve my context card with my identity, voice, business knowledge, working preferences and factual sources. Keep listing-specific facts separate. Do not copy sensitive client details into a general profile.

3. INTERVIEW ME ABOUT EMAIL, COMMUNICATIONS, CALENDAR AND FILES
Find out what I actually use before recommending connections. Ask progressively:
- What is my business email address and email provider? Is it my mailbox or a shared/team inbox? Where do client conversations arrive: email, text, WhatsApp, Teams, Slack or somewhere else?
- Which calendar do I use, which calendars matter for this work, what is my time zone, and what scheduling rules or working hours should you respect?
- Where do contacts, follow-up commitments and transaction notes live: a CRM, Google Contacts, Outlook, a spreadsheet or another system?
- Where do listing documents, photos and approved marketing assets live: Google Drive, OneDrive, Dropbox, local folders or a property platform?
- Which listing, MLS, photo, social or publishing tools matter to the first task? What is already connected to this AI?
Do not ask all of these at once. Start with the systems needed for my chosen first task. My business email is context; never ask me to paste passwords, API keys, recovery codes or tokens into chat.

4. CONNECT THE RIGHT ACCOUNTS WITH ME
Create a short connection plan: system, exact account or workspace, purpose, needed permission and any cost or admin approval requirement. Inspect existing connectors first. Prefer connectors already supported by this AI. Do not pretend to install a connector you cannot access, guess a vendor integration, or subscribe me to a paid service.
For each selected connection, explain the access needed and use the provider's secure sign-in/consent flow. Let me complete account login. If account access requires my IT administrator, mark that connection pending and continue independent work. Menu labels vary: verify the current supported steps, and adapt to what I see.
Start with the narrowest access that works. Reading a selected document or drafting a reply does not authorize sending messages, creating meetings, editing CRM records or publishing content. Ask which future actions I want help with; record the preference without treating it as blanket permission to act.
Test each connection with a small read I choose: locate a selected document, read a chosen email, retrieve a selected contact, or check a specified calendar window. Confirm the account and resource returned. Avoid broad mailbox/contact exports. Never send a test email or create a test event unless I explicitly request it. Report unavailable access separately from an empty result.

5. SAVE MY SETUP AND PROVE ONE SKILL WORKS
Save my context card and a business-connections.md record in the workspace I choose. Record account/provider, purpose, access level, verified/pending/unavailable state, what was tested, time zone and relevant working rules. Record identifiers only when necessary; never store credentials. If you cannot save files, give me downloadable artifacts and say they still need to be saved.
Choose one useful first task with me: draft content in my voice; create a listing launch from verified facts; review a listing photo; or improve my context card. If I do not want to supply client material yet, use the clearly fictional practice listing. Read the relevant installed skill and run the task using available tools. Return an actual editable result, explain review needs and preserve the source facts. Listing photo generation requires a callable image tool: a staging brief is not a finished image.
End with a concise setup receipt: skills installed or session-only; context saved or awaiting save; connectors verified/pending/unavailable and which accounts; first result and where it lives; anything I still need to do; and one simple request I can use next time. Do not mark an installation or connection complete without evidence. Do not fabricate a persistent AIA MCP connection or automatic portal synchronization.
<!-- PROMPT_END -->
