# KOBOT Vibe Coder v1.5.0 (Extreme Edition)

Agentic AI Assistant for Blender 4.0+. Tell it what you want to see, and it will write, execute, and verify the Python code to make it happen. The **Extreme Edition** exposes the cognitive engine of the AI directly to you.

## Installation
1. Install the addon zip in Blender (`Edit > Preferences > Add-ons > Install...`).
2. Enable the addon.
3. If this is your first time, click the **"Install Requirements"** button in the Addon Preferences. This installs the necessary `requests` Python library. You MUST restart Blender after this step.

## Setup & API Keys
You need a Google Gemini API Key to use KOBOT. You can get a free one at Google AI Studio. Paste your API Key into the Addon Preferences.

### Understanding the Modes & Models (No BS Explanation)
The High-Tier AI models cost money or have strict limits. KOBOT gives you two ways to handle this:

* **QUICK Mode (Default):** This is all you need. You have two hardcoded options:
    * **Free Tier / High RPM (Flash):** Use this 99% of the time. It uses the `gemini-2.5-flash` model. It is incredibly fast, smart enough for most Blender scripting, and won't hit rate limits on a free API key during continuous coding.
    * **Paid Tier / Low RPM (Pro):** Use this for complex math or highly specific tasks. It uses `gemini-3.1-pro-preview`. 

    **IMPORTANT:** "Paid Tier" does NOT mean you are paying for KOBOT. It refers to Google's API limits. If you have a free Google key, leave it on the Free Tier (Flash) to avoid Error 429 workflow interruptions.

* **ADVANCED Mode (Extreme Mode):** For developers and hackers. 
    * Click "Fetch Available Models" to query the Google API and populate a dropdown with every experimental model available.
    * **AI Cognitive Settings:** You now have full access to the AI's "brain". Adjust the **Temperature** (0.0 for strict logic, 1.0 for creative coding) and rewrite the **System Prompt** on the fly to force the AI to behave exactly how you want.

## Usage
1. Open the Sidebar in the 3D Viewport (`N` key) and go to the KOBOT tab. You can quickly swap models right here.
2. Type your instruction (e.g., "Create a procedural city with random colors and spin the camera around it").
3. Click EXECUTE.
4. KOBOT will enter its 5-loop Vibe Coder cycle. It writes code, runs it, checks the scene context, and self-corrects if it encounters a Python error or missing objects.

Download: You can clone this repo, or grab the ready-to-install .zip file from Gumroad (Pay what you want) to support the project.

Happy coding.
