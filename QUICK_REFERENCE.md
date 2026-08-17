# Jarvis1 Refactoring Quick Reference

**Print this** 📄 | **Keep it handy** 🎯 | **Follow it** ✅

---

## 🎯 The Problem (In 30 Seconds)

```
Current:  main.py = 1099 lines with hardcoded tools
Goal:     main.py = 200 lines, tools auto-discovered
Benefit:  Add new tool in 5 min (not 30 min)
```

---

## 📋 The 6-Phase Plan

| Phase | What | Time | Why |
|-------|------|------|-----|
| **1** | Module Registry | 1-2w | Foundation for everything |
| **2** | Modularize Tools | 2-3w | Move 40+ tools to modules/ |
| **3** | Tool Executor | 1w | Replace if/elif chains |
| **4** | E-commerce (Shopify) | 2w | 💰 Revenue integration |
| **5** | Trading (Binance) | 2w | 📈 Automate your bot |
| **6** | Docs | 1w | 📚 Make it reproducible |

**Total: ~10-12 weeks to complete refactor + your projects**

---

## 🚀 Start Phase 1 NOW

### Files to Create (Copy-Paste From PHASE1_MODULE_REGISTRY.md)

```
✅ systems/tools/base_module.py      (Base class)
✅ systems/tools/module_registry.py  (Auto-discovery)
✅ systems/tools/tool_executor.py    (Dispatcher)
✅ modules/system/open_app/          (Example module)
✅ modules/system/open_app/module.yaml
```

### Quick Steps

```bash
# 1. Create folders
mkdir -p systems/tools
mkdir -p modules/system/open_app

# 2. Copy files from PHASE1 doc
# base_module.py
# module_registry.py
# tool_executor.py

# 3. Test
python test_phase1.py

# 4. Verify main.py still works
python main.py
```

**Expected:** All 6 tests pass ✅

---

## 📂 Folder Structure (Post-Phase 1)

```
jarvis1/
├── systems/tools/
│   ├── base_module.py         ← NEW
│   ├── module_registry.py      ← NEW
│   └── tool_executor.py        ← NEW
│
├── modules/                    ← NEW
│   ├── system/open_app/        ← EXAMPLE
│   ├── browser/
│   ├── social/
│   ├── ecommerce/              ← PHASE 4
│   ├── trading/                ← PHASE 5
│   └── ...
│
└── main.py                     ← SIMPLIFIED (200 lines)
```

---

## 🎨 Module Template (Memorize This)

```python
# modules/category/toolname/toolname.py

from systems.tools.base_module import BaseModule

class MyToolModule(BaseModule):
    name = "my_tool"
    category = "category"
    
    def execute(self, parameters, context=None):
        try:
            # YOUR CODE HERE
            return {"status": "ok", "data": result}
        except Exception as e:
            return self.handle_error(e, context)
```

```yaml
# modules/category/toolname/module.yaml

name: my_tool
category: category
description: What it does

tools:
  - name: my_tool
    description: Tool description
    parameters:
      type: OBJECT
      properties:
        param1: {type: STRING}
    required: [param1]

enabled: true
```

---

## 🔑 Key Concepts

### Before (Monolithic)
```python
# main.py - 1099 lines
TOOL_DECLARATIONS = [
    {name: "open_app", ...},
    {name: "web_search", ...},
    # ... 50 more
]

async def _execute_tool(self, fc):
    if name == "open_app":
        r = open_app(...)
    elif name == "web_search":
        r = web_search(...)
    elif ...  # 50 elif chains!
```

### After (Modular)
```python
# main.py - 200 lines
registry = get_registry()  # Auto-discovers!
TOOL_DECLARATIONS = registry.get_tool_declarations()

executor = get_executor()
result = await executor.execute(tool_name, parameters, context)
# No more if/elif chains!
```

---

## 📍 Your Projects Integration Points

### Shopify (Phase 4)
```
modules/ecommerce/shopify/
├── shopify.py         (API client)
├── orders.py          (Tool: shopify_orders)
├── products.py        (Tool: shopify_products)
└── module.yaml

Voice: "Shopify orders list kar"
```

### Binance Bot (Phase 5)
```
modules/trading/binance/
├── binance_bot.py     (Bot control)
└── module.yaml

Voice: "Bot start kar 5x BTC par"
```

### Velmora (Phase 4 extension)
```
modules/ecommerce/shopify/
└── velmora_sync.py    (Sync tool)

Voice: "Velmora sync kar"
```

---

## ✅ Checklist: Phase 1

- [ ] Create `systems/tools/base_module.py`
- [ ] Create `systems/tools/module_registry.py`
- [ ] Create `systems/tools/tool_executor.py`
- [ ] Create `modules/system/open_app/` folder + files
- [ ] Create `modules/system/open_app/module.yaml`
- [ ] Update `main.py` to use registry
- [ ] Run `test_phase1.py` (6 tests pass)
- [ ] Verify Jarvis still works (open_app tool)
- [ ] No regressions (existing tools work)
- [ ] Commit to git: "feat: Phase 1 - Module registry"

**Time:** ~4 hours  
**Reward:** Foundation for all future work ✅

---

## 🚨 Common Mistakes (Avoid!)

| Mistake | Fix |
|---------|-----|
| Import path wrong | Check: `modules.category.toolname.toolname` + `__init__.py` |
| module.yaml invalid YAML | Use online YAML validator |
| Class name wrong | Must end with "Module" or explicitly in code |
| Registry not discovering | Check: `enabled: true` in YAML |
| Module not found at runtime | Check folder structure matches import path |

---

## 📊 Impact Dashboard

**Before Phase 1:**
- Adding tool: 30 min (edit main.py, add to declarations, test)
- Tool discovery: None (hardcoded)
- File lines: 1099 in main.py
- Complexity: Very High

**After Phase 1:**
- Adding tool: 5 min (create folder + 3 files)
- Tool discovery: Automatic ✅
- File lines: ~200 in main.py
- Complexity: Modular ✅

---

## 🎓 Learning Resources

Inside jarvis1/:

1. **JARVIS1_REFACTOR_GUIDE.md** - Full architecture analysis
2. **PHASE1_MODULE_REGISTRY.md** - Step-by-step implementation
3. **DANI_PROJECTS_INTEGRATION.md** - Your projects integration
4. **This file** - Quick reference

---

## 🎯 Success = When?

You're done with Phase 1 when:

```
✅ Registry discovers 2+ modules
✅ test_phase1.py: ALL PASS
✅ main.py: ~200 lines (was 1099)
✅ TOOL_DECLARATIONS: Auto-generated
✅ Existing tools work
✅ No errors in logs
```

---

## 💬 Commands For Your Team

```bash
# Check modules loaded
python -c "from systems.tools.module_registry import get_registry; \
           r = get_registry(); print(r.summary())"

# List available tools
python -c "from systems.tools.tool_executor import get_executor; \
           e = get_executor(); print(list(e.list_available_tools().keys()))"

# Test a tool
python -c "from modules.system.open_app import OpenAppModule; \
           m = OpenAppModule(); \
           print(m.execute({'app_name': 'Chrome'}))"

# Run full test suite
python test_phase1.py
```

---

## 🚀 After Phase 1

**Week 2:**  Move 10-15 tools to modules/  
**Week 3:**  Move remaining 25-30 tools  
**Week 4:**  Create Shopify + Trading modules  
**Week 5:**  Integration testing + docs  

---

## 💡 Pro Tips

1. **Keep main.py clean** - Only initialization, no logic
2. **Use context dict** - Pass ui, speak, player through context
3. **Error handling** - Always return `{"status": "error", ...}`
4. **Voice response** - Include "result" key for Gemini
5. **Test locally** - Before adding to registry
6. **Document YAML** - Clear descriptions for Gemini

---

## 🔗 Critical Links

```
your-repo: https://github.com/hk7184398-spec/jarvis1

Documentation files (in repo root):
- JARVIS1_REFACTOR_GUIDE.md
- PHASE1_MODULE_REGISTRY.md
- DANI_PROJECTS_INTEGRATION.md
- This file!
```

---

## 📞 Questions?

Check relevant doc:

- "How do I add a tool?" → PHASE1_MODULE_REGISTRY.md / Task 1.5
- "What's the overall plan?" → JARVIS1_REFACTOR_GUIDE.md
- "How do I integrate Shopify?" → DANI_PROJECTS_INTEGRATION.md
- "What files do I need?" → This file (Quick Reference)

---

## ⏰ Time Investment vs Payoff

**Time: ~10-12 weeks total**

| Phase | Time | Payoff |
|-------|------|--------|
| 1 | 1w | Foundation (enables all future work) |
| 2 | 2w | Organized codebase |
| 3 | 1w | Clean architecture |
| 4 | 2w | **Shopify integration (new revenue!)** |
| 5 | 2w | **Trading automation (passive income!)** |
| 6 | 1w | Documented, reproducible |

**Total ROI:** Very High  
**Urgency:** Start NOW, focus on Phases 1-4 first

---

## 🎯 Focus Areas (For You)

**In Order:**

1. ✅ **Phase 1** (This week!) - Foundation
2. 💰 **Phase 4** (Shopify) - Revenue  
3. 📈 **Phase 5** (Trading) - Automate bot
4. 📚 **Phase 6** (Docs) - Reproducibility

Phases 2-3 are infrastructure but necessary.

---

## 🏁 First Steps (Right Now)

1. Read PHASE1_MODULE_REGISTRY.md (30 min)
2. Create folders & files (1 hour)
3. Run tests (15 min)
4. Commit to git (5 min)
5. Report back! 🎉

**Time to start:** NOW  
**Estimated this week:** 4-6 hours  
**Next week:** Prep Shopify integration

---

**Good luck! You've got this.** 🚀

*Last updated: August 18, 2026*
