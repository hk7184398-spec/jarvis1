# Phase 1: Module Registry & Auto-Discovery Implementation

**Objective:** Enable automatic module discovery without breaking existing code  
**Time:** 1-2 weeks  
**Difficulty:** Medium (refactoring, not new features)  
**Reward:** Foundation for all future work

---

## 📋 What We're Building

```
Before: main.py has hardcoded TOOL_DECLARATIONS with 100+ lines
After:  Registry auto-scans modules/ folder, loads module.yaml files
Result: Add new tools by creating a folder + 3 files (no main.py edit!)
```

---

## 🎯 Phase 1 Tasks (Order Matters!)

### Task 1.1: Create Base Module Class (30 min)

**File:** `systems/tools/base_module.py`

```python
"""Base class for all Jarvis modules"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import traceback


class BaseModule(ABC):
    """All tools inherit from this"""
    
    name: str = None
    category: str = None
    version: str = "1.0"
    description: str = ""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize module
        
        Args:
            config: Dict with module settings from module.yaml
        """
        self.config = config or {}
        self.enabled = True
    
    @abstractmethod
    def execute(self, parameters: Dict[str, Any], context: Optional[Dict] = None) -> Any:
        """
        Execute the tool
        
        Args:
            parameters: Tool parameters from Gemini
            context: Optional context with ui, speak, etc.
        
        Returns:
            Result dict or string
        """
        pass
    
    def validate_parameters(self, parameters: Dict, required: list) -> bool:
        """Validate required parameters are present"""
        for param in required:
            if param not in parameters or parameters[param] is None:
                raise ValueError(f"Missing required parameter: {param}")
        return True
    
    def log(self, message: str, level: str = "INFO"):
        """Log module activity"""
        print(f"[{self.name}] {level}: {message}")
    
    def handle_error(self, error: Exception, context: Optional[Dict] = None) -> Dict:
        """Standard error handling"""
        self.log(f"Error: {error}", level="ERROR")
        traceback.print_exc()
        
        error_msg = str(error)[:200]
        
        # Try to speak error if context has speak function
        if context and "speak" in context:
            try:
                context["speak"](f"Sir, {self.name} error: {error_msg}")
            except:
                pass
        
        return {
            "status": "error",
            "tool": self.name,
            "error": error_msg
        }


class BaseSystemModule(BaseModule):
    """For system-level tools (desktop, files, apps)"""
    pass


class BaseSocialModule(BaseModule):
    """For social media tools (Facebook, TikTok, etc.)"""
    pass


class BaseEcommerceModule(BaseModule):
    """For e-commerce tools (Shopify, Velmora, etc.)"""
    pass


class BaseWebModule(BaseModule):
    """For web tools (search, browser, etc.)"""
    pass


# Example usage:
# 
# class OpenAppModule(BaseSystemModule):
#     name = "open_app"
#     category = "system"
#     description = "Opens any application"
#     
#     def execute(self, parameters, context=None):
#         app_name = parameters.get("app_name")
#         # implementation
#         return {"status": "opened", "app": app_name}
```

---

### Task 1.2: Create Module Registry (45 min)

**File:** `systems/tools/module_registry.py`

```python
"""Auto-discovers and manages all Jarvis modules"""
import yaml
import importlib
from pathlib import Path
from typing import Dict, List, Optional, Any
import traceback


class ModuleRegistry:
    """
    Central registry for all tools/modules.
    
    Workflow:
    1. Scan modules/ for folders with module.yaml
    2. Load module.yaml specs
    3. Dynamically import module classes
    4. Create instances and register
    5. Serve TOOL_DECLARATIONS to Gemini
    """
    
    def __init__(self, modules_dir: Path):
        self.modules_dir = modules_dir
        self.modules: Dict[str, Any] = {}  # name -> module instance
        self.tools: Dict[str, Dict] = {}   # tool_name -> tool spec
        self.specs: Dict[str, Dict] = {}   # name -> module.yaml content
    
    def discover(self) -> bool:
        """
        Scan modules/ directory and load all modules
        
        Returns:
            True if successful
        """
        print(f"[Registry] 🔍 Discovering modules in {self.modules_dir}")
        
        if not self.modules_dir.exists():
            print(f"[Registry] ⚠️  Modules directory not found: {self.modules_dir}")
            return False
        
        count = 0
        for category_dir in self.modules_dir.iterdir():
            if not category_dir.is_dir() or category_dir.name.startswith("_"):
                continue
            
            for module_dir in category_dir.iterdir():
                if not module_dir.is_dir() or module_dir.name.startswith("_"):
                    continue
                
                yaml_file = module_dir / "module.yaml"
                if yaml_file.exists():
                    if self._load_module(module_dir, yaml_file):
                        count += 1
        
        print(f"[Registry] ✅ Loaded {count} modules")
        return True
    
    def _load_module(self, module_dir: Path, yaml_file: Path) -> bool:
        """Load a single module from its folder"""
        try:
            # 1. Read module.yaml
            with open(yaml_file) as f:
                spec = yaml.safe_load(f)
            
            module_name = spec.get("name")
            if not module_name:
                print(f"[Registry] ⚠️  No name in {yaml_file}")
                return False
            
            # Check if enabled
            if not spec.get("enabled", True):
                print(f"[Registry] ⏸️  {module_name} disabled")
                return True  # Don't load, but not an error
            
            # 2. Import module class
            module_class = self._import_module_class(module_dir, module_name)
            if not module_class:
                return False
            
            # 3. Instantiate module
            config = spec.get("config", {})
            instance = module_class(config=config)
            
            # 4. Register module
            self.modules[module_name] = instance
            self.specs[module_name] = spec
            
            # 5. Register all tools from this module
            for tool_spec in spec.get("tools", []):
                tool_name = tool_spec.get("name")
                if tool_name:
                    self.tools[tool_name] = {
                        **tool_spec,
                        "__module_name": module_name  # Track which module owns it
                    }
            
            print(f"[Registry] ✅ {module_name} ({len(spec.get('tools', []))} tools)")
            return True
        
        except Exception as e:
            print(f"[Registry] ❌ Failed to load {yaml_file}: {e}")
            traceback.print_exc()
            return False
    
    def _import_module_class(self, module_dir: Path, module_name: str):
        """Dynamically import module class"""
        try:
            # Convert path to Python module path
            # modules/system/open_app -> modules.system.open_app
            category = module_dir.parent.name
            rel_path = f"modules.{category}.{module_name}.{module_name}"
            
            module = importlib.import_module(rel_path)
            
            # Find class that inherits from BaseModule
            # Convention: module file has class named ModuleNameModule
            class_name = "".join(w.capitalize() for w in module_name.split("_")) + "Module"
            
            if hasattr(module, class_name):
                cls = getattr(module, class_name)
                return cls
            
            # Fallback: look for any BaseModule subclass
            from systems.tools.base_module import BaseModule
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and issubclass(obj, BaseModule) and obj != BaseModule:
                    return obj
            
            print(f"[Registry] ⚠️  No BaseModule class in {module_name}")
            return None
        
        except Exception as e:
            print(f"[Registry] ❌ Failed to import {module_name}: {e}")
            return None
    
    def get_tool_declarations(self) -> List[Dict]:
        """
        Get TOOL_DECLARATIONS for Gemini Live
        
        Returns:
            List of tool specs in Gemini format
        """
        declarations = []
        
        for tool_name, tool_spec in self.tools.items():
            # Extract Gemini-specific fields
            declaration = {
                "name": tool_spec.get("name"),
                "description": tool_spec.get("description", ""),
                "parameters": tool_spec.get("parameters", {})
            }
            declarations.append(declaration)
        
        return declarations
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict]:
        """Get metadata for a specific tool"""
        return self.tools.get(tool_name)
    
    def get_module_for_tool(self, tool_name: str) -> Optional[Any]:
        """Get module instance that handles a tool"""
        tool_spec = self.tools.get(tool_name)
        if not tool_spec:
            return None
        
        module_name = tool_spec.get("__module_name")
        return self.modules.get(module_name)
    
    def list_modules(self) -> Dict[str, Dict]:
        """List all loaded modules and their tools"""
        result = {}
        for module_name, instance in self.modules.items():
            tools = [t for t in self.tools if self.tools[t].get("__module_name") == module_name]
            result[module_name] = {
                "class": instance.__class__.__name__,
                "category": instance.category,
                "tools": tools,
                "enabled": instance.enabled
            }
        return result
    
    def reload_module(self, module_name: str) -> bool:
        """Reload a single module (for development)"""
        # Implementation for hot-reload (Phase 2)
        pass
    
    def summary(self) -> str:
        """Get human-readable summary"""
        lines = [
            f"Jarvis1 Module Registry",
            f"Modules: {len(self.modules)}",
            f"Tools: {len(self.tools)}",
            ""
        ]
        
        for module_name in sorted(self.modules.keys()):
            tools = [t for t in self.tools if self.tools[t].get("__module_name") == module_name]
            lines.append(f"  • {module_name}: {len(tools)} tools")
        
        return "\n".join(lines)


# Global registry (instantiated in main.py)
_global_registry = None


def get_registry() -> ModuleRegistry:
    """Get or create global registry"""
    global _global_registry
    if _global_registry is None:
        from core.paths import BASE_DIR
        modules_dir = BASE_DIR / "modules"
        _global_registry = ModuleRegistry(modules_dir)
        _global_registry.discover()
    return _global_registry


def reset_registry():
    """Reset registry (for testing)"""
    global _global_registry
    _global_registry = None
```

---

### Task 1.3: Create module.yaml Template (15 min)

**File:** `modules/TEMPLATE_module.yaml` (template for copy-paste)

```yaml
# Module configuration template
# Copy this file to your module folder and update

name: tool_name
version: 1.0
category: system  # system | browser | social | ecommerce | trading | content | utility
description: Brief description of what this module does

# Tools provided by this module
tools:
  - name: tool_name
    description: What this tool does
    parameters:
      type: OBJECT
      properties:
        param1:
          type: STRING
          description: Description of param1
        param2:
          type: INTEGER
          description: Description of param2
      required: [param1]  # List required parameters

# Python package dependencies (auto-installed? - future feature)
dependencies:
  - requests
  - beautifulsoup4

# Module-specific configuration
config:
  timeout: 30
  retries: 3
  debug: false

# Enable/disable without deleting folder
enabled: true
```

---

### Task 1.4: Create Tool Executor (45 min)

**File:** `systems/tools/tool_executor.py`

```python
"""Universal tool executor - replaces the elif chains in main.py"""
import asyncio
from typing import Dict, Any, Optional, Callable
from systems.tools.module_registry import get_registry


class ToolExecutor:
    """
    Central dispatcher for all tool calls.
    
    Replaces this (main.py):
        if name == "open_app":
            r = open_app(...)
        elif name == "web_search":
            r = web_search(...)
        elif name == "facebook_post":
            r = facebook_post(...)
        # ... 50 more elif chains!
    
    With this:
        executor = ToolExecutor()
        result = await executor.execute("tool_name", parameters, context)
    """
    
    def __init__(self):
        self.registry = get_registry()
        self.execution_count = 0
        self.error_count = 0
    
    async def execute(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        loop = None
    ) -> str:
        """
        Execute a tool by name
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool
            context: Context dict with ui, speak, player, etc.
            loop: asyncio event loop (for executor.run_in_executor)
        
        Returns:
            Result as string (for Gemini)
        """
        self.execution_count += 1
        
        try:
            # Get the module that handles this tool
            module = self.registry.get_module_for_tool(tool_name)
            if not module:
                error = f"Tool not found: {tool_name}"
                print(f"[ToolExecutor] ❌ {error}")
                self.error_count += 1
                return error
            
            print(f"[ToolExecutor] 🔧 {tool_name} (module: {module.name})")
            
            # Special handling for async/blocking tools
            if loop is None:
                loop = asyncio.get_event_loop()
            
            # Run module.execute() in thread pool
            result = await loop.run_in_executor(
                None,
                lambda: module.execute(parameters, context=context)
            )
            
            # Convert result to string for Gemini
            if isinstance(result, dict):
                if result.get("status") == "error":
                    return result.get("error", "Unknown error")
                return result.get("result", str(result))
            
            return str(result) if result else "Done."
        
        except Exception as e:
            error_msg = f"Tool execution failed: {e}"
            print(f"[ToolExecutor] ❌ {error_msg}")
            self.error_count += 1
            
            # Try to notify via context
            if context and "speak" in context:
                try:
                    context["speak"](f"Sir, tool execution error: {str(e)[:100]}")
                except:
                    pass
            
            return error_msg
    
    def validate_tool_exists(self, tool_name: str) -> bool:
        """Check if tool exists in registry"""
        return tool_name in self.registry.tools
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict]:
        """Get tool specification"""
        return self.registry.get_tool_info(tool_name)
    
    def list_available_tools(self) -> Dict[str, str]:
        """List all available tools with descriptions"""
        return {
            name: spec.get("description", "")
            for name, spec in self.registry.tools.items()
        }
    
    def get_stats(self) -> Dict:
        """Get executor statistics"""
        return {
            "total_executions": self.execution_count,
            "total_errors": self.error_count,
            "error_rate": (self.error_count / self.execution_count * 100) if self.execution_count > 0 else 0,
            "tools_available": len(self.registry.tools),
            "modules_loaded": len(self.registry.modules)
        }


# Global executor instance
_executor = None


def get_executor() -> ToolExecutor:
    """Get or create global executor"""
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor
```

---

### Task 1.5: Create First Module (as example) (30 min)

**Folder structure:**
```
modules/system/open_app/
├── __init__.py
├── open_app.py
└── module.yaml
```

**File:** `modules/system/open_app/module.yaml`

```yaml
name: open_app
version: 1.0
category: system
description: Opens any application on the computer

tools:
  - name: open_app
    description: Opens applications, websites, or programs
    parameters:
      type: OBJECT
      properties:
        app_name:
          type: STRING
          description: Name of application (e.g. 'Chrome', 'WhatsApp', 'Spotify')
        chat_name:
          type: STRING
          description: Optional - contact name to open inside messaging app
      required: [app_name]

dependencies:
  - pyautogui
  - psutil

config:
  timeout: 10
  verify_launch: true

enabled: true
```

**File:** `modules/system/open_app/__init__.py`

```python
from .open_app import OpenAppModule

__all__ = ["OpenAppModule"]
```

**File:** `modules/system/open_app/open_app.py`

```python
from systems.tools.base_module import BaseSystemModule
from typing import Dict, Any, Optional


class OpenAppModule(BaseSystemModule):
    """Opens any application on the computer"""
    
    name = "open_app"
    category = "system"
    version = "1.0"
    description = "Opens applications, websites, or programs"
    
    def execute(self, parameters: Dict[str, Any], context: Optional[Dict] = None) -> Dict:
        """
        Open an application
        
        Args:
            parameters: {app_name: str, chat_name: optional str}
            context: UI/player context
        
        Returns:
            {status: "opened", app: app_name}
        """
        try:
            app_name = parameters.get("app_name", "").strip()
            chat_name = parameters.get("chat_name", "").strip()
            
            if not app_name:
                return {"status": "error", "error": "app_name is required"}
            
            # TODO: Move existing implementation from actions/open_app.py here
            # This is a placeholder showing structure
            
            self.log(f"Opening app: {app_name}")
            
            # Existing implementation from actions/open_app.py
            # ... (copy the open_app function body here)
            
            return {
                "status": "opened",
                "app": app_name,
                "chat": chat_name if chat_name else None
            }
        
        except Exception as e:
            return self.handle_error(e, context)
```

---

### Task 1.6: Update main.py to Use Registry (30 min)

**Change this (current main.py):**

```python
TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": "Opens any application...",
        "parameters": { ... }
    },
    {
        "name": "web_search",
        "description": "Searches the web...",
        "parameters": { ... }
    },
    # ... 50+ more lines
]

# Later in JarvisLive._execute_tool():
async def _execute_tool(self, fc):
    if name == "open_app":
        r = open_app(...)
    elif name == "web_search":
        r = web_search(...)
    elif name == "facebook_post":
        r = facebook_post(...)
    # ... elif elif elif ...
```

**To this (new main.py):**

```python
# At top of main.py
from systems.tools.module_registry import get_registry
from systems.tools.tool_executor import get_executor

# In _build_config():
def _build_config(self) -> types.LiveConnectConfig:
    # ... existing code ...
    
    # Get tool declarations from registry
    registry = get_registry()
    TOOL_DECLARATIONS = registry.get_tool_declarations()
    
    print(registry.summary())  # Print registry info
    
    return types.LiveConnectConfig(
        # ... rest stays same ...
        tools=[{"function_declarations": TOOL_DECLARATIONS}],
    )

# In _execute_tool():
async def _execute_tool(self, fc) -> types.FunctionResponse:
    name = fc.name
    args = dict(fc.args or {})
    
    print(f"[JARVIS] 🔧 {name} {args}")
    self.ui.set_state("THINKING")
    
    # NEW: Use executor instead of elif chains!
    executor = get_executor()
    result = await executor.execute(
        tool_name=name,
        parameters=args,
        context={
            "ui": self.ui,
            "speak": self.speak,
            "player": self.ui
        },
        loop=asyncio.get_event_loop()
    )
    
    # Save to memory if needed
    if name == "save_memory":
        # Handle save_memory specially (existing code)
        pass
    
    if not self.ui.muted:
        self.ui.set_state("LISTENING")
    
    print(f"[JARVIS] 📤 {name} → {str(result)[:80]}")
    
    return types.FunctionResponse(
        id=fc.id, name=name,
        response={"result": result}
    )
```

---

### Task 1.7: Testing Checklist (1 hour)

```python
# test_phase1.py - Run this to verify everything works

import pytest
from pathlib import Path
from systems.tools.module_registry import ModuleRegistry, get_registry
from systems.tools.tool_executor import ToolExecutor, get_executor

def test_registry_discovery():
    """Test that registry discovers modules"""
    registry = get_registry()
    
    assert len(registry.modules) > 0, "No modules discovered"
    assert len(registry.tools) > 0, "No tools discovered"
    print(f"✅ Found {len(registry.modules)} modules, {len(registry.tools)} tools")

def test_get_declarations():
    """Test tool declarations format"""
    registry = get_registry()
    declarations = registry.get_tool_declarations()
    
    assert isinstance(declarations, list)
    assert all("name" in d for d in declarations)
    assert all("description" in d for d in declarations)
    print(f"✅ Valid tool declarations for {len(declarations)} tools")

def test_executor_exists():
    """Test executor can be instantiated"""
    executor = get_executor()
    
    assert executor is not None
    assert executor.registry is not None
    print("✅ Executor initialized")

def test_tool_lookup():
    """Test finding tools"""
    executor = get_executor()
    
    # Open_app should exist
    assert executor.validate_tool_exists("open_app")
    info = executor.get_tool_info("open_app")
    assert info is not None
    print(f"✅ open_app tool found: {info.get('description')}")

def test_module_for_tool():
    """Test getting module for tool"""
    registry = get_registry()
    module = registry.get_module_for_tool("open_app")
    
    assert module is not None
    assert hasattr(module, 'execute')
    print(f"✅ Module for open_app: {module.__class__.__name__}")

def test_registry_summary():
    """Test registry summary output"""
    registry = get_registry()
    summary = registry.summary()
    
    assert "Module Registry" in summary
    assert "Modules:" in summary
    assert "Tools:" in summary
    print("✅ Summary output:")
    print(summary)

if __name__ == "__main__":
    print("\n🧪 Running Phase 1 Tests...\n")
    test_registry_discovery()
    test_get_declarations()
    test_executor_exists()
    test_tool_lookup()
    test_module_for_tool()
    test_registry_summary()
    print("\n✅ All Phase 1 tests passed!\n")
```

**Run tests:**
```bash
cd jarvis1
python test_phase1.py
```

Expected output:
```
🧪 Running Phase 1 Tests...

✅ Found 2 modules, 1 tools
✅ Valid tool declarations for 1 tools
✅ Executor initialized
✅ open_app tool found: Opens any application on the computer
✅ Module for open_app: OpenAppModule
✅ Summary output:
Jarvis1 Module Registry
Modules: 2
Tools: 1

  • open_app: 1 tools

✅ All Phase 1 tests passed!
```

---

## 📂 File Structure After Phase 1

```
jarvis1/
├── core/
│   ├── gemini.py
│   ├── config.py
│   └── paths.py
│
├── systems/
│   └── tools/              ← NEW!
│       ├── __init__.py
│       ├── base_module.py  ← NEW: BaseModule class
│       ├── module_registry.py ← NEW: Auto-discovery
│       ├── tool_executor.py ← NEW: Central dispatcher
│       └── tool_cache.py    ← NEW: Caching layer (optional)
│
├── modules/                ← NEW!
│   ├── system/
│   │   └── open_app/
│   │       ├── __init__.py
│   │       ├── open_app.py (moved from actions/)
│   │       └── module.yaml ← NEW!
│   │
│   ├── browser/            ← Will move tools here
│   ├── social/             ← Will move tools here
│   ├── ecommerce/          ← Will create in Phase 4
│   ├── trading/            ← Will create in Phase 5
│   ├── content/            ← Will move tools here
│   └── utility/            ← Will move tools here
│
├── ui/
│   ├── main_ui.py
│   └── widgets/
│
├── config/
│   ├── .env
│   ├── mcp_servers.json
│   └── skills.json
│
├── main.py                 ← NOW: ~200 lines, not 1099!
├── requirements.txt
└── test_phase1.py          ← NEW: Verification tests
```

---

## 🚀 How to Execute Phase 1

### Step 1: Prep (15 min)
```bash
cd jarvis1

# Create new directories
mkdir -p systems/tools
mkdir -p modules/system/open_app

# Copy TEMPLATE_module.yaml for reference
touch modules/TEMPLATE_module.yaml
```

### Step 2: Implement (2 hours)
1. Create `systems/tools/base_module.py` (copy from Task 1.1)
2. Create `systems/tools/module_registry.py` (copy from Task 1.2)
3. Create `systems/tools/tool_executor.py` (copy from Task 1.4)
4. Create template YAML (copy from Task 1.3)
5. Create first module: `modules/system/open_app/` (copy from Task 1.5)

### Step 3: Test (30 min)
```bash
# Run tests
python test_phase1.py

# Expected: All tests pass ✅
```

### Step 4: Integrate (1 hour)
```bash
# Update main.py to use registry (Task 1.6)
# Test by running Jarvis and using a tool
python main.py

# Verify it still works!
# Test voice: "Open Chrome"
# Should use registry now
```

### Step 5: Verify No Regression (30 min)
- [ ] Voice input works
- [ ] open_app tool still functions
- [ ] Multiple tools work
- [ ] Memory still saves
- [ ] Error handling still works

---

## ✅ Definition of Done (Phase 1)

Phase 1 is complete when:

- [x] BaseModule class created and working
- [x] ModuleRegistry discovers at least 1 module from module.yaml
- [x] ToolExecutor works without hardcoded elif chains
- [x] First module (open_app) migrated to new structure
- [x] main.py uses registry (down from 1099 to ~200 lines)
- [x] TOOL_DECLARATIONS auto-generated from registry
- [x] All existing tools still work (no regression)
- [x] Tests pass
- [x] Documentation updated

---

## 🎓 Key Concepts Introduced

### Module System
- Each tool lives in its own folder
- module.yaml declares what it does
- Python class inherits from BaseModule
- execute() method is the interface

### Registry Pattern
- Scan modules/ directory
- Load YAML specs
- Dynamically import classes
- Register tools centrally
- Serve to Gemini

### Executor Pattern
- Central dispatcher (not if/elif chains)
- Context passing (ui, speak, etc.)
- Error handling
- Async support

### Benefits
- ✅ Add tool without editing main.py
- ✅ Easy to find where a tool is implemented
- ✅ Can disable tools via YAML
- ✅ Auto-documentation
- ✅ Testing becomes easier
- ✅ Future: Hot-reload in dev mode

---

## ⏱️ Estimated Time Breakdown

| Task | Time | Notes |
|------|------|-------|
| 1.1: Base Module | 30 min | Straightforward ABC class |
| 1.2: Registry | 45 min | Most complex part |
| 1.3: YAML Template | 15 min | Copy-paste |
| 1.4: Executor | 45 min | Replace elif chains |
| 1.5: First Module | 30 min | Example implementation |
| 1.6: Update main.py | 30 min | Integration |
| 1.7: Testing | 1 hour | Verification |
| **Total** | **~4 hours** | One dev session |

**After this:** You're ready for Phase 2 (migrate remaining 40+ tools).

---

## 🚨 Common Pitfalls

1. **Import paths wrong**
   - If import fails, check: `modules.category.toolname.toolname`
   - Each folder needs `__init__.py`

2. **module.yaml syntax**
   - Must be valid YAML (no tabs, proper indentation)
   - Validate with: `python -c "import yaml; yaml.safe_load(open('module.yaml'))"`

3. **Tool spec format**
   - Must match Gemini's expected format
   - Look at existing actions/ for reference

4. **Circular imports**
   - Don't import main.py in modules
   - Use context dict for communication

5. **Registry not discovering**
   - Check folder structure: `modules/category/toolname/module.yaml`
   - Check `enabled: true` in YAML
   - Check class name ends with "Module"

---

## 🎯 Next Steps After Phase 1

Once Phase 1 is solid:

1. **Phase 2:** Migrate remaining 40+ tools to modules/
2. **Phase 3:** Create central tool executor (already done in Phase 1!)
3. **Phase 4:** Add Shopify/e-commerce modules
4. **Phase 5:** Add Trading/Binance modules
5. **Phase 6:** Documentation

---

**You've got this!** Start with Task 1.1 and work through them in order. Each task builds on the previous one.

Good luck! 🚀
