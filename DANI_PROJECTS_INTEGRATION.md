# 🎯 Dani's Projects Integration Guide

**Focus:** Your active projects (Shopify, Binance Bot, Velmora) → Jarvis1  
**Status:** Currently isolated, will be integrated into Jarvis core  
**Benefit:** Voice control everything from one AI assistant  

---

## 📊 Current State of Your Projects

### 1. Shopify E-commerce (NEW FOCUS)
```
Status: ❌ NOT INTEGRATED
Location: None yet (from your memory: "Shopify Admin API integration for Jarvis")
Capability: Needs to exist
Problem: Jarvis can't access orders, inventory, customer data
```

### 2. Binance Futures Trading Bot (ACTIVE)
```
Status: 🔴 ISOLATED
Location: Windows, Python-based
Dependencies: RSI/MACD/Bollinger Bands, Flask dashboard
Problem: 
  - Runs separately from Jarvis
  - Can't be controlled by voice
  - Dependency issues on Windows (Python 3.12)
  - No integration with Jarvis memory/UI
```

### 3. Velmora E-commerce Platform (STANDALONE)
```
Status: 🔴 ISOLATED  
Location: Separate Node.js/Express project
Features: JazzCash, EasyPaisa payments, Temu-style UI
Problem:
  - Disconnected from Jarvis
  - No inventory sync with Shopify
  - No order monitoring from Jarvis
```

### 4. Jarvis1 (MAIN SYSTEM)
```
Status: ✅ WORKING
Capabilities: Voice, file handling, social media, screen control
Missing: E-commerce, trading, system integration
```

---

## 🎯 Integration Plan (Your Projects)

### Phase 4A: Shopify Integration (Priority 1)

**Goal:** Jarvis can monitor orders, inventory, customers, payments

**New Module:** `modules/ecommerce/shopify/`

```
modules/ecommerce/shopify/
├── __init__.py
├── shopify.py              (Main client)
├── orders.py               (Order monitoring)
├── products.py             (Product/inventory)
├── customers.py            (Customer data)
├── payments.py             (Payment status)
├── analytics.py            (Sales reports)
└── module.yaml
```

**Step 1: Create Shopify client wrapper**

```python
# modules/ecommerce/shopify/shopify.py
import requests
from typing import Dict, List, Optional
from datetime import datetime

class ShopifyClient:
    """Shopify Admin API wrapper"""
    
    def __init__(self, shop_name: str, access_token: str, api_version: str = "2025-01"):
        """
        Initialize Shopify client
        
        Args:
            shop_name: Your shop name (without .myshopify.com)
            access_token: Admin API access token (from Shopify Partner)
            api_version: API version (2025-01, etc.)
        """
        self.shop_name = shop_name
        self.access_token = access_token
        self.api_version = api_version
        self.base_url = f"https://{shop_name}.myshopify.com/admin/api/{api_version}"
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json"
        }
    
    def get_orders(self, status: str = "any", limit: int = 10) -> List[Dict]:
        """
        Get recent orders
        
        Args:
            status: any | pending | processing | shipped | completed | cancelled
            limit: Number of orders to return
        
        Returns:
            List of order dicts
        """
        url = f"{self.base_url}/orders.json"
        params = {
            "status": status,
            "limit": limit,
            "fields": "id,order_number,created_at,email,total_price,financial_status,fulfillment_status,line_items"
        }
        
        try:
            resp = requests.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            return resp.json().get("orders", [])
        except Exception as e:
            raise Exception(f"Failed to get orders: {e}")
    
    def get_order(self, order_id: str) -> Dict:
        """Get single order details"""
        url = f"{self.base_url}/orders/{order_id}.json"
        try:
            resp = requests.get(url, headers=self.headers)
            resp.raise_for_status()
            return resp.json().get("order", {})
        except Exception as e:
            raise Exception(f"Failed to get order {order_id}: {e}")
    
    def get_products(self, limit: int = 10) -> List[Dict]:
        """Get products (with inventory)"""
        url = f"{self.base_url}/products.json"
        params = {
            "limit": limit,
            "fields": "id,title,handle,status,variants"
        }
        
        try:
            resp = requests.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            return resp.json().get("products", [])
        except Exception as e:
            raise Exception(f"Failed to get products: {e}")
    
    def get_inventory_level(self, product_id: str) -> Dict:
        """Get inventory for product"""
        # Requires fetching variants + inventory levels
        product = self.get_product(product_id)
        result = {}
        
        for variant in product.get("variants", []):
            result[variant["title"]] = {
                "inventory_quantity": variant.get("inventory_quantity", 0),
                "sku": variant.get("sku", "N/A")
            }
        
        return result
    
    def get_sales_stats(self, days: int = 7) -> Dict:
        """Get sales stats for last N days"""
        orders = self.get_orders(status="any", limit=250)
        
        recent = [
            o for o in orders
            if self._is_recent(o.get("created_at"), days)
        ]
        
        total_sales = sum(float(o.get("total_price", 0)) for o in recent)
        
        return {
            "period_days": days,
            "orders": len(recent),
            "total_sales": total_sales,
            "avg_order_value": total_sales / len(recent) if recent else 0
        }
    
    @staticmethod
    def _is_recent(date_str: str, days: int) -> bool:
        """Check if date is within N days"""
        from datetime import timedelta
        date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        cutoff = datetime.now(date.tzinfo) - timedelta(days=days)
        return date > cutoff
```

**Step 2: Create Shopify Orders module**

```python
# modules/ecommerce/shopify/orders.py
from systems.tools.base_module import BaseEcommerceModule
from typing import Dict, Any, Optional
from .shopify import ShopifyClient
from core.config import get_config

class ShopifyOrdersModule(BaseEcommerceModule):
    """Monitor Shopify orders"""
    
    name = "shopify_orders"
    category = "ecommerce"
    version = "1.0"
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.client = self._init_client()
    
    def _init_client(self) -> ShopifyClient:
        """Initialize Shopify client from config"""
        cfg = get_config()
        return ShopifyClient(
            shop_name=cfg.get("SHOPIFY_SHOP_NAME"),
            access_token=cfg.get("SHOPIFY_ACCESS_TOKEN")
        )
    
    def execute(self, parameters: Dict[str, Any], context: Optional[Dict] = None) -> Dict:
        """
        Execute order-related actions
        
        Parameters:
            action: list | get | update_status | stats
            limit: Number of orders (default: 10)
            status: pending | processing | completed (default: any)
            order_id: For get/update actions
        """
        try:
            action = parameters.get("action", "list")
            
            if action == "list":
                return self._list_orders(parameters)
            elif action == "get":
                return self._get_order(parameters)
            elif action == "update_status":
                return self._update_status(parameters)
            elif action == "stats":
                return self._get_stats(parameters)
            else:
                return {"error": f"Unknown action: {action}"}
        
        except Exception as e:
            return self.handle_error(e, context)
    
    def _list_orders(self, params: Dict) -> Dict:
        """List orders"""
        status = params.get("status", "any")
        limit = params.get("limit", 10)
        
        orders = self.client.get_orders(status=status, limit=limit)
        
        formatted = []
        for order in orders:
            formatted.append({
                "id": order["id"],
                "number": order["order_number"],
                "customer": order.get("email", "Guest"),
                "total": order["total_price"],
                "status": order["fulfillment_status"],
                "payment": order["financial_status"],
                "date": order["created_at"][:10]
            })
        
        return {
            "status": "ok",
            "orders": formatted,
            "count": len(formatted),
            "result": self._format_voice_response(formatted)
        }
    
    def _get_order(self, params: Dict) -> Dict:
        """Get order details"""
        order_id = params.get("order_id")
        if not order_id:
            return {"error": "order_id required"}
        
        order = self.client.get_order(order_id)
        
        items = [
            f"{li['quantity']}x {li['title']}"
            for li in order.get("line_items", [])
        ]
        
        return {
            "status": "ok",
            "order": {
                "id": order["id"],
                "number": order["order_number"],
                "customer": order.get("customer", {}).get("email"),
                "items": items,
                "total": order["total_price"],
                "payment_status": order["financial_status"],
                "fulfillment_status": order["fulfillment_status"]
            },
            "result": self._format_order_detail(order)
        }
    
    def _update_status(self, params: Dict) -> Dict:
        """Update order status (requires Shopify API v2025+)"""
        # TODO: Implement order status update
        return {"error": "Not yet implemented"}
    
    def _get_stats(self, params: Dict) -> Dict:
        """Get sales statistics"""
        days = params.get("days", 7)
        stats = self.client.get_sales_stats(days=days)
        
        return {
            "status": "ok",
            "stats": stats,
            "result": f"{stats['orders']} orders in last {days} days. Total: ${stats['total_sales']:.2f}"
        }
    
    @staticmethod
    def _format_voice_response(orders: list) -> str:
        """Format orders for voice response"""
        if not orders:
            return "You have no orders."
        
        lines = [f"You have {len(orders)} orders:"]
        for o in orders[:3]:  # Speak first 3
            lines.append(f"  • Order {o['number']}: ${o['total']} - {o['status']}")
        
        if len(orders) > 3:
            lines.append(f"  • ...and {len(orders) - 3} more")
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_order_detail(order: Dict) -> str:
        """Format single order for voice"""
        lines = [f"Order #{order['order_number']}"]
        lines.append(f"Customer: {order.get('customer', {}).get('email', 'Unknown')}")
        lines.append(f"Total: ${order['total_price']}")
        lines.append(f"Status: {order['fulfillment_status']}")
        
        return "\n".join(lines)
```

**Step 3: Create module.yaml**

```yaml
# modules/ecommerce/shopify/module.yaml
name: shopify_orders
version: 1.0
category: ecommerce
description: Monitor and manage Shopify orders

tools:
  - name: shopify_orders
    description: List orders, get order details, check sales stats
    parameters:
      type: OBJECT
      properties:
        action:
          type: STRING
          description: "list | get | update_status | stats"
        status:
          type: STRING
          description: "any | pending | processing | completed"
        limit:
          type: INTEGER
          description: "Number of orders (default: 10)"
        order_id:
          type: STRING
          description: "Order ID for get/update"
        days:
          type: INTEGER
          description: "Days for stats (default: 7)"
      required: [action]

dependencies:
  - requests

config:
  api_version: "2025-01"
  timeout: 30
  retry_count: 3

enabled: true
```

---

### Phase 4B: Connect to Velmora (Part of Shopify integration)

**New tool:** `shopify_velmora_sync`

```python
# modules/ecommerce/shopify/velmora_sync.py

class VelmoraSyncModule(BaseEcommerceModule):
    """Sync Shopify with Velmora Node.js backend"""
    
    name = "velmora_sync"
    
    def execute(self, parameters: Dict[str, Any], context: Optional[Dict] = None) -> Dict:
        """
        Sync between Shopify and Velmora
        
        Actions:
        - sync_products: Push Shopify products to Velmora
        - sync_orders: Pull orders from Shopify to Velmora
        - check_status: Verify sync status
        """
        action = parameters.get("action")
        
        if action == "sync_products":
            return self._sync_products()
        elif action == "sync_orders":
            return self._sync_orders()
        elif action == "check_status":
            return self._check_status()
```

---

### Phase 5: Binance Trading Bot Integration (Priority 2)

**Goal:** Voice-control your trading bot from Jarvis

**Current Issue:** Bot runs on Windows, separate process, Flask dashboard

**Solution:** Wrap bot in module, communicate via REST API

**New Module:** `modules/trading/binance/`

```
modules/trading/binance/
├── __init__.py
├── binance_bot.py          (Bot wrapper)
├── portfolio_monitor.py    (P&L tracking)
├── alerts.py              (Price alerts)
└── module.yaml
```

**Step 1: Wrap Binance Bot as REST API (if not already)**

```python
# Your existing bot should expose:
# GET /api/bot/status
# POST /api/bot/start
# POST /api/bot/stop
# GET /api/portfolio/pnl
```

**Step 2: Create Binance module**

```python
# modules/trading/binance/binance_bot.py
from systems.tools.base_module import BaseModule
import requests
from typing import Dict, Any, Optional

class BinanceBotModule(BaseModule):
    """Control Binance Futures trading bot"""
    
    name = "binance_bot"
    category = "trading"
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.bot_url = config.get("bot_api_url", "http://localhost:5000")
    
    def execute(self, parameters: Dict[str, Any], context: Optional[Dict] = None) -> Dict:
        """
        Control bot
        
        Actions:
        - status: Check if bot running
        - start: Start trading
        - stop: Stop trading
        - adjust: Change leverage/pair
        - pnl: Get current P&L
        """
        try:
            action = parameters.get("action", "status")
            
            if action == "status":
                return self._get_status()
            elif action == "start":
                return self._start_bot(parameters)
            elif action == "stop":
                return self._stop_bot()
            elif action == "pnl":
                return self._get_pnl()
            elif action == "adjust":
                return self._adjust_params(parameters)
        
        except Exception as e:
            return self.handle_error(e, context)
    
    def _get_status(self) -> Dict:
        """Get bot status"""
        try:
            resp = requests.get(f"{self.bot_url}/api/bot/status", timeout=5)
            data = resp.json()
            
            return {
                "status": "ok",
                "running": data.get("is_running"),
                "pair": data.get("pair"),
                "leverage": data.get("leverage"),
                "result": f"Bot {'running' if data.get('is_running') else 'stopped'} on {data.get('pair')} at {data.get('leverage')}x"
            }
        except Exception as e:
            return {"status": "error", "error": f"Bot unreachable: {e}"}
    
    def _start_bot(self, params: Dict) -> Dict:
        """Start trading bot"""
        payload = {
            "pair": params.get("pair", "BTCUSDT"),
            "leverage": params.get("leverage", 5),
            "strategy": params.get("strategy", "RSI")
        }
        
        try:
            resp = requests.post(f"{self.bot_url}/api/bot/start", json=payload, timeout=10)
            data = resp.json()
            
            return {
                "status": "ok",
                "running": True,
                "result": f"Bot started on {payload['pair']} with {payload['leverage']}x leverage"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _stop_bot(self) -> Dict:
        """Stop trading bot"""
        try:
            resp = requests.post(f"{self.bot_url}/api/bot/stop", timeout=10)
            return {
                "status": "ok",
                "result": "Bot stopped"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _get_pnl(self) -> Dict:
        """Get current P&L"""
        try:
            resp = requests.get(f"{self.bot_url}/api/portfolio/pnl", timeout=5)
            data = resp.json()
            
            pnl = float(data.get("pnl_usd", 0))
            pnl_pct = float(data.get("pnl_pct", 0))
            
            return {
                "status": "ok",
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "result": f"P&L: ${pnl:.2f} ({pnl_pct:+.2f}%)"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _adjust_params(self, params: Dict) -> Dict:
        """Adjust bot parameters"""
        payload = {
            "leverage": params.get("leverage"),
            "strategy": params.get("strategy")
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        try:
            resp = requests.post(f"{self.bot_url}/api/bot/adjust", json=payload, timeout=10)
            return {
                "status": "ok",
                "result": f"Bot adjusted: {payload}"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
```

**Step 3: Create module.yaml for Binance**

```yaml
# modules/trading/binance/module.yaml
name: binance_bot
version: 1.0
category: trading
description: Control Binance Futures trading bot

tools:
  - name: binance_bot
    description: Start/stop trading bot, check status and P&L
    parameters:
      type: OBJECT
      properties:
        action:
          type: STRING
          description: "status | start | stop | pnl | adjust"
        pair:
          type: STRING
          description: "Trading pair (e.g. BTCUSDT, XAUUSD)"
        leverage:
          type: INTEGER
          description: "Leverage (1-10x)"
        strategy:
          type: STRING
          description: "Trading strategy (RSI, MACD, etc.)"
      required: [action]

dependencies:
  - requests

config:
  bot_api_url: "http://localhost:5000"
  timeout: 10

enabled: true
```

---

## 🗣️ Voice Commands Examples (After Integration)

### Shopify Commands
```
User: "Shopify par kitne orders hain?"
Jarvis: [calls shopify_orders with action=list]
Jarvis: "You have 5 orders: Order #1001 ($150 - processing), Order #1002 ($89 - pending)..."

User: "Last week ki sales batao"
Jarvis: [calls shopify_orders with action=stats, days=7]
Jarvis: "18 orders in last 7 days. Total sales: $2,340"

User: "Order 1001 ke details"
Jarvis: [calls shopify_orders with action=get, order_id=1001]
Jarvis: "Order #1001: Customer john@example.com, 2x Product Name, Total $150, Status: Processing"

User: "Inventory check kar"
Jarvis: [calls shopify_products]
Jarvis: "Product A: 45 in stock, Product B: 12 in stock, Product C: Out of stock"
```

### Trading Commands
```
User: "Bot status"
Jarvis: [calls binance_bot with action=status]
Jarvis: "Bot running on BTCUSDT at 5x leverage"

User: "Bot start kar, BTC par 5x"
Jarvis: [calls binance_bot with action=start, pair=BTCUSDT, leverage=5]
Jarvis: "Bot started on BTCUSDT with 5x leverage"

User: "Current P&L kya hai?"
Jarvis: [calls binance_bot with action=pnl]
Jarvis: "P&L: +$450.25 (+2.15%)"

User: "Bot band kar"
Jarvis: [calls binance_bot with action=stop]
Jarvis: "Bot stopped"
```

### Velmora Commands
```
User: "Velmora par kitne products listed hain?"
Jarvis: [calls velmora_sync or velmora_dashboard]
Jarvis: "152 products listed on Velmora"

User: "New products Shopify se import kar"
Jarvis: [calls velmora_sync with action=sync_products]
Jarvis: "Synced 23 new products from Shopify"
```

---

## ⚙️ Configuration Requirements

### .env file (or config.yaml)

```bash
# Shopify
SHOPIFY_SHOP_NAME=your-shop
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx
SHOPIFY_API_VERSION=2025-01

# Binance Bot
BINANCE_BOT_URL=http://localhost:5000
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

# Velmora (if separate)
VELMORA_API_URL=http://localhost:3000
VELMORA_API_KEY=your_key
```

### In modules/ecommerce/shopify/module.yaml
```yaml
config:
  shop_name: ${SHOPIFY_SHOP_NAME}
  access_token: ${SHOPIFY_ACCESS_TOKEN}
  api_version: ${SHOPIFY_API_VERSION}
```

---

## 📋 Implementation Order

### Week 1: Shopify
1. [x] Create Shopify client wrapper
2. [x] Create ShopifyOrdersModule
3. [x] Create module.yaml
4. [x] Test: "List orders"
5. [x] Add ShopifyProductsModule
6. [x] Test: "Inventory check"

### Week 2: Velmora Sync
1. [x] Connect Velmora API
2. [x] Create VelmoraSyncModule
3. [x] Sync products Shopify → Velmora
4. [x] Test: Voice sync commands

### Week 3: Binance Bot
1. [x] Wrap Binance bot as REST API
2. [x] Create BinanceBotModule
3. [x] Test: Bot status/start/stop
4. [x] Add portfolio monitoring

### Week 4+: Polish & Documentation
1. [x] Error handling
2. [x] Logging
3. [x] Documentation
4. [x] Integration testing

---

## 🎯 Success Metrics

After integration, you should be able to:

```
✅ Voice: "Shopify orders list kar"
   → Get order count, recent orders, status breakdown
   
✅ Voice: "Bot start kar 5x BTC par"
   → Bot starts trading
   
✅ Voice: "Current profit?"
   → P&L displayed and spoken
   
✅ Voice: "Velmora sync kar"
   → Products/orders synced

✅ Main.py stays under 300 lines (modular)

✅ Add new tool in <10 min (just create module folder)

✅ No regression (existing tools still work)
```

---

## 🚀 Next Steps

1. **After Phase 1 (Registry):** Start this integration
2. **Priority:** Shopify first (e-commerce = $$$)
3. **Then:** Trading bot (existing interest)
4. **Last:** Polish + documentation

Good luck! Your Jarvis1 is about to become a true multi-capability assistant. 🤖

---

**Questions?** This guide is designed specifically for your workflow. Adapt as needed!
