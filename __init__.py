bl_info = {
    "name": "KOBOT: AI Copilot (Extreme Edition 1.5.0)",
    "author": "KOBOT & Gemini",
    "version": (1, 5, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > KOBOT",
    "description": "Agentic AI with exposed Model, Temperature, and Prompt settings.",
    "warning": "",
    "doc_url": "",
    "category": "AI",
}

import bpy
import json
import re
import threading
import queue
import os
import time
import sys
import subprocess
import textwrap
from bpy.app.handlers import persistent

# --- DEPENDENCY CHECK ---
try:
    import requests
    DEPENDENCY_INSTALLED = True
except ImportError:
    requests = None
    DEPENDENCY_INSTALLED = False

# --- CONFIGURATION ---
HISTORY_FILE = os.path.join(os.path.expanduser("~"), "kobot_history.txt")
execution_queue = queue.Queue()

# --- MODEL LISTS ---
quick_models = [
    ("gemini-2.5-flash", "Free Tier / High RPM (Flash)", "Best for continuous coding"),
    ("gemini-3.1-pro-preview", "Paid Tier / Low RPM (Pro)", "Best for complex reasoning")
]
available_models = [("gemini-2.5-flash", "Gemini 2.5 Flash", "Default Advanced Model")]

def get_quick_model_items(self, context):
    return quick_models

def get_advanced_model_items(self, context):
    return available_models

# --- STATUS HELPER ---
def set_kobot_status(props, msg):
    props.chat_history = msg
    props.history_lines.clear()
    for paragraph in msg.split('\n'):
        if paragraph.strip():
            for line in textwrap.wrap(paragraph.strip(), width=55):
                item = props.history_lines.add()
                item.text = line

# --- UNDO HANDLER ---
@persistent
def reset_kobot_state(scene):
    try:
        props = bpy.context.scene.kobot_props
        if props.is_working:
            props.is_working = False
            set_kobot_status(props, "Ready (Undo detected).")
    except: pass

# --- OPERATORS ---
class KOBOT_OT_InstallDeps(bpy.types.Operator):
    bl_idname = "kobot.install_deps"
    bl_label = "Install Requirements"
    def execute(self, context):
        try:
            python_exe = sys.executable
            subprocess.check_call([python_exe, "-m", "ensurepip"])
            subprocess.check_call([python_exe, "-m", "pip", "install", "requests"])
            self.report({'INFO'}, "Installation Complete! Please RESTART Blender.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Install Failed: {str(e)}")
            return {'CANCELLED'}

class KOBOT_OT_RefreshModels(bpy.types.Operator):
    bl_idname = "kobot.refresh_models"
    bl_label = "Fetch Available Models"
    def execute(self, context):
        if not DEPENDENCY_INSTALLED: return {'CANCELLED'}
        prefs = context.preferences.addons[__name__].preferences
        key = prefs.api_key
        if not key:
            self.report({'ERROR'}, "API Key required.")
            return {'CANCELLED'}
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                global available_models
                new_list = []
                for m in data.get('models', []):
                    if "generateContent" in m.get('supportedGenerationMethods', []):
                        raw_name = m['name'].replace("models/", "")
                        nice_name = raw_name.replace("gemini-", "").replace("-", " ").title()
                        new_list.append((raw_name, nice_name, ""))
                new_list.sort(key=lambda x: x[0], reverse=True)
                if not any(x[0] == 'gemini-2.5-flash' for x in new_list):
                    new_list.insert(0, ("gemini-2.5-flash", "Gemini 2.5 Flash", ""))
                available_models = new_list
                self.report({'INFO'}, f"Found {len(new_list)} models.")
            else:
                self.report({'ERROR'}, f"API Error: {response.status_code}")
        except Exception as e:
            self.report({'ERROR'}, f"Connection Error: {str(e)}")
        return {'FINISHED'}

# --- PREFERENCES ---
class KobotPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    
    api_key: bpy.props.StringProperty(name="API Key", subtype='PASSWORD')
    
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("QUICK", "Quick Setup", "Standard usage"),
            ("ADVANCED", "Advanced Mode", "Full control")
        ],
        default="QUICK"
    )
    quick_tier: bpy.props.EnumProperty(name="Tier", items=get_quick_model_items, default=0)
    advanced_model: bpy.props.EnumProperty(name="Model", items=get_advanced_model_items, default=0)
    
    # EXTREME MODE PROPERTIES
    temperature: bpy.props.FloatProperty(
        name="Temperature", 
        description="0.0 = Strict/Robotic, 1.0 = Creative/Vibe, 2.0 = Chaos", 
        default=0.7, min=0.0, max=2.0
    )
    
    system_prompt: bpy.props.StringProperty(
        name="System Prompt",
        description="The hidden master prompt instructing the AI how to behave",
        default="You are KOBOT, an elite pragmatic Blender Python technical artist. Your ONLY goal is to deliver the visual payload efficiently.\nRULES:\n1. Output ONLY executable Python code wrapped in ```python blocks. Zero conversational text.\n2. Focus on the visual result. Use robust methods.\n3. Keep the code concise but bulletproof.",
        options={'HIDDEN'} 
    )
    
    def draw(self, context):
        layout = self.layout
        if not DEPENDENCY_INSTALLED:
            layout.box().operator("kobot.install_deps", text="Install Requirements", icon='IMPORT')
            return

        main_box = layout.box()
        main_box.prop(self, "api_key")
        main_box.row().prop(self, "mode", expand=True)
        
        if self.mode == 'QUICK':
            quick_box = layout.box()
            quick_box.prop(self, "quick_tier")
        else:
            adv_box = layout.box()
            row = adv_box.row()
            row.prop(self, "advanced_model")
            row.operator("kobot.refresh_models", text="", icon='FILE_REFRESH')
            
            # Draw Extreme Mode Settings
            extreme_box = layout.box()
            extreme_box.label(text="AI Cognitive Settings (Extreme Edition):", icon='OUTLINER_OB_LIGHT')
            extreme_box.prop(self, "temperature")
            extreme_box.label(text="System Prompt:")
            extreme_box.prop(self, "system_prompt", text="")

# --- ENGINE ---
def log_to_file(text):
    try:
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {text}\n")
    except: pass

def get_scene_context():
    try: return str([o.name for o in bpy.context.scene.objects[:25]])
    except: return "Unknown Context"

def get_active_model():
    prefs = bpy.context.preferences.addons[__name__].preferences
    return prefs.quick_tier if prefs.mode == 'QUICK' else prefs.advanced_model

def ask_gemini_raw(api_key, model, prompt, temp):
    if not DEPENDENCY_INSTALLED: return "ERROR", "Deps missing"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temp}
    }
    
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=45)
            if response.status_code == 503: 
                time.sleep(2)
                continue
            if response.status_code != 200: 
                return "ERROR", f"HTTP {response.status_code}: {response.text}"
            
            data = response.json()
            if 'candidates' not in data: return "ERROR", "Empty response"
            parts = data['candidates'][0]['content'].get('parts', [])
            full_reply = "".join([p.get('text', '') for p in parts])
            return "OK", full_reply
        except Exception as e:
            time.sleep(1)
    return "ERROR", "Connection failed."

# --- WORKER THREAD ---
def ai_worker(api_key, model, full_prompt, attempt, original_req, temp):
    try:
        status, reply = ask_gemini_raw(api_key, model, full_prompt, temp)
        
        if status != "OK":
            execution_queue.put(("ERROR", reply))
            return

        if attempt > 1 and "[DONE]" in reply:
            msg = reply.split("[DONE]")[-1].strip()
            execution_queue.put(("DONE", msg if msg else "Task Complete!"))
        elif attempt > 1 and "[GIVE_UP]" in reply:
            msg = reply.split("[GIVE_UP]")[-1].strip()
            execution_queue.put(("GIVE_UP", msg if msg else "AI gave up."))
        else:
            match = re.search(r"```python(.*?)```", reply, re.DOTALL)
            if match:
                code = match.group(1).strip()
                execution_queue.put(("EXECUTE", code, attempt, original_req, full_prompt, reply))
            else:
                if attempt == 1:
                    execution_queue.put(("ERROR", "Lazy AI Bug: Only text returned."))
                else:
                    execution_queue.put(("GIVE_UP", "AI did not return Python code."))
    except Exception as e:
        execution_queue.put(("ERROR", f"Thread Exception: {str(e)}"))

# --- MAIN LOOP ---
def check_queue():
    try:
        while not execution_queue.empty():
            item = execution_queue.get_nowait()
            msg_type = item[0]
            props = bpy.context.scene.kobot_props
            prefs = bpy.context.preferences.addons[__name__].preferences
            
            if msg_type in ["ERROR", "DONE", "GIVE_UP"]:
                set_kobot_status(props, f"{msg_type}: {item[1]}")
                props.is_working = False
                force_ui_update()
                return None
                
            elif msg_type == "EXECUTE":
                code, attempt, original_req, past_prompt, ai_reply = item[1], item[2], item[3], item[4], item[5]
                result_msg = ""
                
                try:
                    if attempt == 1: bpy.ops.ed.undo_push(message=f"KOBOT: {original_req}")
                    exec_globals = {'bpy': bpy, 'math': __import__('math'), 'C': bpy.context, 'D': bpy.data}
                    exec(code, exec_globals)
                    result_msg = "SUCCESS: Code executed."
                except Exception as e:
                    result_msg = f"PYTHON ERROR: {str(e)}"
                    
                if attempt >= 5:
                    set_kobot_status(props, f"Timeout after 5 loops. Result: {result_msg[:50]}...")
                    props.is_working = False
                    force_ui_update()
                    return None
                
                props.retry_count = attempt
                set_kobot_status(props, f"Verifying Phase (Loop {attempt}/5)...")
                force_ui_update()
                
                new_ctx = get_scene_context()
                verify_prompt = (
                    f"{past_prompt}\n\nAI Code:\n```python\n{code}\n```\n\n"
                    f"--- EXECUTION REPORT (LOOP {attempt}) ---\n"
                    f"Result: {result_msg}\n"
                    f"Current Objects: {new_ctx}\n\n"
                    f"EVALUATION PROTOCOL:\n"
                    f"1. Did the code achieve the visual payload? (Ignore minor console warnings if 3D result is correct).\n"
                    f"2. If SUCCESS: Output exactly `[DONE]` followed by a cool victory message.\n"
                    f"3. If FAILED: Output ONLY new Python code in ```python blocks.\n"
                    f"4. If impossible: Output exactly `[GIVE_UP]`."
                )
                
                active_model = get_active_model()
                thread = threading.Thread(target=ai_worker, args=(prefs.api_key, active_model, verify_prompt, attempt + 1, original_req, prefs.temperature))
                thread.start()
                return 0.5
                
    except Exception as e: pass
    return 0.5

def force_ui_update():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D': area.tag_redraw()

class KOBOT_OT_RemoveHistoryLine(bpy.types.Operator):
    bl_idname = "kobot.remove_history_line"
    bl_label = "Remove Log Line"
    index: bpy.props.IntProperty()
    def execute(self, context):
        props = context.scene.kobot_props
        if 0 <= self.index < len(props.history_lines):
            props.history_lines.remove(self.index)
        return {'FINISHED'}

# --- MAIN RUN OPERATOR ---
class KOBOT_OT_SendAI(bpy.types.Operator):
    bl_idname = "kobot.send_ai"
    bl_label = "Run"
    def execute(self, context):
        if not DEPENDENCY_INSTALLED: return {'CANCELLED'}
        prefs = context.preferences.addons[__name__].preferences
        if not prefs.api_key: return {'CANCELLED'}
        
        props = context.scene.kobot_props
        user_req = props.user_prompt
        if not user_req.strip(): return {'CANCELLED'}

        props.is_working = True
        set_kobot_status(props, "Thinking (Loop 1/5)...")
        props.retry_count = 1
        
        full_prompt = f"{prefs.system_prompt}\n\nInitial Scene Context: {get_scene_context()}\nUser Request: {user_req}"
        
        active_model = get_active_model()
        thread = threading.Thread(target=ai_worker, args=(prefs.api_key, active_model, full_prompt, 1, user_req, prefs.temperature))
        thread.start()
        
        if not bpy.app.timers.is_registered(check_queue):
            bpy.app.timers.register(check_queue)
        return {'FINISHED'}

# --- PANEL ---
class KobotHistoryLine(bpy.types.PropertyGroup):
    text: bpy.props.StringProperty()

class KobotProperties(bpy.types.PropertyGroup):
    user_prompt: bpy.props.StringProperty(name="", default="")
    chat_history: bpy.props.StringProperty(name="Status", default="Ready")
    history_lines: bpy.props.CollectionProperty(type=KobotHistoryLine)
    is_working: bpy.props.BoolProperty(default=False)
    retry_count: bpy.props.IntProperty(default=0)

class KOBOT_PT_MainPanel(bpy.types.Panel):
    bl_label = "KOBOT AI"
    bl_idname = "KOBOT_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'KOBOT'

    def draw(self, context):
        layout = self.layout
        if not DEPENDENCY_INSTALLED:
            layout.label(text="Setup Required!", icon='ERROR')
            return

        props = context.scene.kobot_props
        prefs = context.preferences.addons[__name__].preferences
        
        # TIER SELECTOR IN MAIN UI
        ui_box = layout.box()
        if prefs.mode == 'QUICK':
            ui_box.prop(prefs, "quick_tier", text="")
        else:
            ui_box.prop(prefs, "advanced_model", text="")
            
        box = layout.box()
        if props.is_working:
            box.label(text=f"Agent Processing (Loop {props.retry_count}/5)...", icon='TIME')
        
        if len(props.history_lines) == 0:
            box.label(text="Ready", icon='INFO')
        else:
            for i, item in enumerate(props.history_lines):
                row = box.row(align=True)
                row.prop(item, "text", text="", icon='INFO')
                op = row.operator("kobot.remove_history_line", text="", icon='CANCEL')
                op.index = i
            
        layout.separator()
        
        layout.label(text="Instruction:")
        col = layout.box().column(align=True)
        col.scale_y = 1.2
        col.prop(props, "user_prompt", text="", icon='CONSOLE') 
        
        row = layout.row()
        row.enabled = not props.is_working
        row.scale_y = 1.5
        row.operator("kobot.send_ai", text="EXECUTE", icon='PLAY')

# --- REGISTRATION ---
classes = (KobotPreferences, KobotHistoryLine, KobotProperties, KOBOT_OT_RemoveHistoryLine, KOBOT_OT_SendAI, KOBOT_OT_InstallDeps, KOBOT_OT_RefreshModels, KOBOT_PT_MainPanel)

def register():
    for cls in classes: bpy.utils.register_class(cls)
    bpy.types.Scene.kobot_props = bpy.props.PointerProperty(type=KobotProperties)
    if reset_kobot_state not in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.append(reset_kobot_state)
    if reset_kobot_state not in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.append(reset_kobot_state)

def unregister():
    if reset_kobot_state in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(reset_kobot_state)
    if reset_kobot_state in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.remove(reset_kobot_state)
    del bpy.types.Scene.kobot_props
    for cls in classes: bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()