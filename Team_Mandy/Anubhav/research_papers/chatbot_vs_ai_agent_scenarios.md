# Chatbot vs. AI-Agent — Problem Scenarios

*Task 2 backlog item — 5 scenarios best solved by a Chatbot, 5 best solved by an AI Agent, with reasoning.*

The dividing line used throughout: a **chatbot** answers/guides within a single conversational turn-cycle using a knowledge base, with no autonomous multi-step action or write-access to external systems. An **AI agent** plans across multiple steps, calls tools, reads/writes to real systems, and carries state toward a goal without a human doing each step manually.

---

## A. Scenarios Where a Chatbot Is the Best (and Sufficient) Solution

### 1. Business FAQ / Policy Lookup
**Scenario:** Customers ask about business hours, return policy, shipping costs, or store locations.
**Why chatbot:** The answer already exists verbatim in a knowledge base. There's no action to take and no system to update — retrieval + a well-phrased answer is the entire job. Adding agentic tool-use here is unnecessary complexity and cost.

### 2. Product Recommendation Quiz
**Scenario:** A retail website asks a few qualifying questions ("skin type?", "budget?") and suggests matching products.
**Why chatbot:** It's a fixed decision tree / single-pass reasoning task over a catalog. It doesn't need to place an order, check live inventory across warehouses, or negotiate — it just needs to converse and recommend.

### 3. Internal HR Policy Q&A
**Scenario:** Employees ask "How many sick days do I have?" or "What's the parental leave policy?"
**Why chatbot:** This is document-grounded Q&A (RAG over the HR handbook). No write access to HR systems is needed, and giving a chatbot read-only knowledge-base access is far lower-risk than granting an agent write access to HR records for a task that never required writing anything.

### 4. Restaurant Info Line (Hours, Menu, Allergens)
**Scenario:** "Are you open on Sundays?", "Do you have a gluten-free menu?"
**Why chatbot:** Purely informational. Contrast with actually booking a table (see Agent scenario 2) — that crosses into needing real-world state changes, which is where a chatbot's job ends.

### 5. SaaS Product Onboarding Walkthrough
**Scenario:** A new user asks "How do I invite teammates?" or "Where do I change my billing plan?" while exploring a new tool.
**Why chatbot:** The user is the one taking the action (clicking through the UI); the bot's job is purely to explain and guide, not to perform account changes on the user's behalf.

---

## B. Scenarios Where an AI Agent Is the Best Solution

### 1. Automated Invoice Reconciliation
**Scenario:** Incoming vendor invoices need to be matched against purchase orders, discrepancies flagged, and approved invoices pushed into the accounting system.
**Why agent:** Requires reading from email/document storage, cross-referencing multiple systems (PO system, accounting software), applying judgment on mismatches, and writing results back — a multi-step, multi-tool workflow a chatbot's single-turn Q&A model can't perform.

### 2. IT Helpdesk Password Reset & Ticketing
**Scenario:** "I'm locked out of my account" needs identity verification, an actual directory reset (e.g., Active Directory/Okta), and a logged, auditable ticket.
**Why agent:** The bot must authenticate the user, call an API to perform the reset, and write an audit record — real actions with real consequences, not just an explanation of the steps.

### 3. Recruiting Pipeline Coordination
**Scenario:** Screen incoming resumes against a role, shortlist candidates, check interviewer calendar availability, schedule interviews, and update the ATS.
**Why agent:** Spans multiple systems (resume database, calendar, ATS, email) and multiple sequential decisions that depend on each other's outcomes — classic multi-step orchestration an agent is built for.

### 4. Inventory Reordering & Supply Chain Monitoring
**Scenario:** Continuously monitor stock levels, compare vendor pricing/lead times, and autonomously place purchase orders within a budget threshold.
**Why agent:** This runs proactively (not user-initiated per turn), pulls live data from multiple sources, makes a judgment call, and executes a real transaction — well beyond answering a question when asked.

### 5. Regulatory/AML Transaction Monitoring (Banking)
**Scenario:** Continuously scan transactions against anti-money-laundering rules, investigate flagged patterns by pulling data from multiple internal systems, and escalate/file reports for human review.
**Why agent:** Needs autonomous, ongoing multi-source investigation and the ability to take a structured next action (escalate, file, close) based on evidence gathered across steps — not a single answer to a single question. (This is the same category of work as the `research` agent already set up in this repo: multi-step tool use, evidence gathering, structured output.)

---

## C. Quick Decision Rule for Future Scenarios

Ask two questions:
1. **Does answering the question require taking a real action or touching a live system (booking, resetting, ordering, updating a record)?** If no → chatbot is sufficient.
2. **Does solving it require multiple dependent steps across more than one data source or tool, where later steps depend on earlier results?** If yes → it needs an agent, not a chatbot.

If both answers point the same direction, that's your solution. If they conflict (e.g., single action but multi-source lookup first), lean toward an agent — it can always behave like a simple chatbot for easy cases, but a chatbot cannot take autonomous action when the scenario demands it.
