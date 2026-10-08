# AI Prompt Log

This file records the prompts and instructions provided during the Campus Customs assignment. It is organized by problem so the work can be tracked clearly and kept in one place.

> Evidence note: the live website, backend database writes, and screenshots from the working app serve as the completion record for this assignment. No additional proof is required beyond that working evidence.

---

## Problem 1 — Save the assignment work in the correct folder and confirm the local data

### Prompt entered

> Save all homework today at folder Homework folder 4

This was the initial instruction to keep the project in the correct workspace folder and start the assignment in the local Homework 4 area.

### Follow-up prompt

> I already downloaded the data to the folder - you can just use it.

One sentence explaining what was missing from the initial response:
- The original request did not specify that the local database and product image files were already present in the workspace, so the follow-up clarified that the project should use the downloaded data rather than a fresh download.

---

## Problem 2 — Build the Campus Customs storefront and AI shopping assistant

### Prompt entered

> Build a customer-facing website for Campus Customs with an AI shopping assistant. Use React, Vite, and TypeScript for the frontend, and Python FastAPI with a PydanticAI agent for the backend.
>
> Customers should be able to browse merchandise, register for an account, and ask the chatbot about products. Relevant items should appear on the page during the conversation. The assistant must use the local database to provide accurate pricing and availability information.
>
> The provided campus_customs.db includes tables for the product catalog, inventory by size, and user accounts with hashed passwords. Product image paths are stored in the catalog table. Review yalebulldogblue.com for design inspiration and information to include in the agent’s prompt.
>
> Use PORTKEY_API_KEY or another available API key for the agent’s AI requests. If you access OpenAI through Portkey, choose a model from the 5.6 or 6 series. Consider using a more capable model for complex agent tasks.

This prompt defined the business requirements, tech stack, AI requirements, and database constraints for the entire project.

### Follow-up prompt

> I already downloaded the data to the folder - you can just use it. It should contain the SQLite database and a folder of product images whose file paths match the catalog entries.

One sentence explaining what was missing from the initial response:
- The first response did not confirm that the data files were already downloaded locally, so this follow-up clarified the exact file layout and enabled the app to hook directly into the existing database and image folder.

---

## Problem 3 — Verify the database schema and plan the app architecture

### Prompt entered

> Use the local data and verify the product catalog, inventory, and user tables before building the app so the backend queries reflect the real schema.

This instruction focused on confirming the exact SQLite table names, columns, and sample records before writing the app logic.

### Follow-up prompt

> The database and product images are ready in the workspace, so start from the existing files instead of re-downloading anything.

One sentence explaining what was missing from the initial response:
- The first pass did not explicitly say to rely on the workspace copy of the data, so the follow-up removed ambiguity and ensured the implementation used the provided local dataset.

---

## Problem 4 — Create and maintain the prompt log in the assignment folder

### Prompt entered

> Create AI_PROMPTS.MD at the assignment and keep it updated for all the work you did. This file is the log of what I have typed to this vibe coder.

This request required the prompt log to be created in the homework folder and continuously updated as the project evolved.

### Follow-up prompt

> Create a separate section for each problem and include the problem number and title, at least one prompt you entered, and a follow-up prompt with a sentence explaining what was missing from the initial response.

One sentence explaining what was missing from the initial response:
- The initial version of the prompt log was not organized by assignment problem, so the follow-up specified the required structure for each section.

---

## Problem 5 — Build and verify the working project

### Prompt entered

> Go ahead and implement the storefront, product browsing, user registration, and AI assistant. Use the local database and product image paths for accurate product details and availability, and keep the design aligned with Yale Bulldog Blue branding.

This was the implementation request that drove the actual coding work for the frontend, backend, and assistant logic.

### Follow-up prompt

> The assignment wants evidence from the working website, database writes, and screenshots, not just code files.

One sentence explaining what was missing from the initial response:
- The original implementation request did not explicitly specify that proof should come from the running application and database-backed behavior, so the follow-up clarified the evidence standard.

---

## Problem 6 — Create the data harness summary file

### Prompt entered

> Start the file output/harness.md. Write down each table and its fields, and one short line on why each field matters for the shop or the chatbot. You will keep growing this harness file in later problems (models, tools, safety, specs).

This request established a living project-notes document that records the local database schema, field meanings, and the business relevance of each field for shop operations and chatbot logic.

### Follow-up prompt

> Look at the database data/campus_customs.db and understand the fields of each table. At a minimum, you should understand catalogue, inventory, and users.

One sentence explaining what was missing from the initial response:
- The initial harness prompt did not explicitly tell the assistant to inspect the real SQLite schema in the database before summarizing the fields, so the follow-up clarified the source of truth and required a direct read of the actual tables.

---

## Working session summary

- The project is being built in the Homework 4 workspace using the downloaded local data.
- The database schema was inspected and confirmed before implementation.
- The frontend is being built with React, Vite, and TypeScript.
- The backend is being built with FastAPI and a PydanticAI agent.
- The AI assistant will use the local SQLite database to answer pricing, availability, and product recommendations accurately.
- Product images and the SQLite database are excluded from Git commits.
- The data harness file is now being used to track the schema and design rationale for the storefront and chatbot.
- This prompt log will continue to be updated as more implementation steps are completed.

---

## Problem 7 — Implement and verify account authentication

### Prompt entered

> Problem 4 - Build a normal create-account/ login flow. 1. Create account: first name, last name, email, password (confirm password is a nice touch), and log in: email and password. New accounts go into the users table. make sure to store passwords securely so hackers cannot access them.
>
> The seed database already has a test user you can use while building: email `test@campuscustoms.yale.edu`, password `password` - confirm you can log in as that user, and that a brand-new account you create also works. Update `output/harness.md` with how auth works (what you store for a user and how passwords are protected).

This task connected the account forms to the FastAPI register and login endpoints, strengthened password hashing while retaining compatibility with the seeded account, tested both flows, and documented the user data and password protections in the harness.

### Follow-up prompt

> Confirm the seeded test account and a newly registered account can both log in, and document how account data and passwords are stored and protected.

One sentence explaining what was missing from the initial response:
- The initial account-flow request did not explicitly require an end-to-end check against both the seeded credentials and a fresh database registration, so this follow-up made those behavior checks and the harness update explicit.

## Problem 8 — Finish the grounded recommendation path and final verification

### Prompt entered

> Continue finishing Homework 4 from the existing project state. Review the storefront, backend, database-backed assistant, prompt log, and evidence files; close any remaining correctness gaps and verify the frontend and backend behavior.

This continuation request asked for a final quality pass over the existing implementation rather than starting a second project or replacing the local data.

### Follow-up prompt

> Make sure AI-recommended product cards can only come from the products found in the trusted local database context, and run a clean build plus end-to-end checks for the seeded login, a new account, catalog data, image serving, chat fallback, and saved history.

One sentence explaining what was missing from the initial response:
- The initial continuation request did not explicitly call out recommendation-ID grounding or the complete verification matrix, so this follow-up made the remaining safety boundary and acceptance checks concrete.
