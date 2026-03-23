# 🔄 Frontend-Backend Sync Documentation

## Overview

Este documento descreve todas as sincronizações implementadas entre o Frontend React e o Backend FastAPI.

---

## 1. 📡 API Endpoints Mapeados

### Kill Switch API (`killSwitchApi`)
| Endpoint | Método | Frontend Function |
|----------|--------|-------------------|
| `/api/emergency/status` | GET | `getStatus()` |
| `/api/emergency/activate` | POST | `activate(data)` |
| `/api/emergency/stop-bot/{botId}` | POST | `stopBot(botId)` |

### License API (`licenseApi`)
| Endpoint | Método | Frontend Function |
|----------|--------|-------------------|
| `/license/plans` | GET | `getPlans()` |
| `/license/my-plan` | GET | `getMyPlan()` |
| `/license/upgrade` | POST | `upgrade(planId)` |
| `/license/activate-trial` | POST | `activateTrial()` |

### 2FA API (`twoFactorApi`)
| Endpoint | Método | Frontend Function |
|----------|--------|-------------------|
| `/auth/2fa/setup` | POST | `setup()` |
| `/auth/2fa/confirm` | POST | `confirm(code)` |
| `/auth/2fa/verify` | POST | `verify(code)` |
| `/auth/2fa/disable` | POST | `disable(code, password)` |
| `/auth/2fa/status` | GET | `getStatus()` |
| `/auth/2fa/backup-codes` | POST | `generateBackupCodes(code)` |
| `/auth/sessions` | GET | `getSessions()` |
| `/auth/sessions/{id}` | DELETE | `revokeSession(id)` |
| `/auth/sessions/revoke-all` | POST | `revokeAllSessions()` |

### PnL Audit API (`auditApi`)
| Endpoint | Método | Frontend Function |
|----------|--------|-------------------|
| `/audit/pnl/summary` | GET | `getPnLSummary(period)` |
| `/audit/pnl/history` | GET | `getPnLHistory(period)` |
| `/audit/trades` | GET | `getTrades(params)` |

### Education API (`educationApi`)
| Endpoint | Método | Frontend Function |
|----------|--------|-------------------|
| `/education/courses` | GET | `getCourses(params)` |
| `/education/courses/{id}` | GET | `getCourse(id)` |
| `/education/courses/{id}/lessons` | GET | `getCourseLessons(id)` |
| `/education/lessons/{id}` | GET | `getLesson(id)` |
| `/education/courses/{id}/enroll` | POST | `enroll(id)` |
| `/education/my-courses` | GET | `getMyCourses()` |
| `/education/progress` | POST | `updateProgress(lessonId, completed)` |

### Affiliates API (`affiliateApi`)
| Endpoint | Método | Frontend Function |
|----------|--------|-------------------|
| `/affiliates/me` | GET | `getMe()` |
| `/affiliates/generate-code` | POST | `generateCode()` |
| `/affiliates/stats` | GET | `getStats()` |
| `/affiliates/referrals` | GET | `getReferrals(params)` |
| `/affiliates/validate/{code}` | GET | `validateCode(code)` |
| `/affiliates/tiers` | GET | `getTiers()` |

### System Health API (`systemApi`)
| Endpoint | Método | Frontend Function |
|----------|--------|-------------------|
| `/validation/health/detailed` | GET | `getHealth()` |
| `/health` | GET | `ping()` |

### Settings API (`settingsApi`)
| Endpoint | Método | Frontend Function |
|----------|--------|-------------------|
| `/settings/profile` | GET/PUT | `getProfile()` / `updateProfile(data)` |
| `/settings/exchanges` | GET/POST | `getExchanges()` / `addExchange(data)` |
| `/settings/exchanges/{exchange}` | DELETE | `deleteExchange(exchange)` |
| `/settings/exchanges/{exchange}/validate` | POST | `validateExchange(exchange)` |
| `/settings/webhooks` | GET/PUT | `getWebhooks()` / `updateWebhooks(data)` |

---

## 2. 🔌 WebSocket Hooks

### `useTradingWebSocket(clientType)`
- **URL**: `ws://localhost:8000/bots/ws/{clientType}`
- **Events**: `trade_update`, `kline_update`, `robot_status`
- **Returns**: `{ isConnected, trades, klineData, robotStatus, sendMessage }`

### `useSystemHealthWebSocket()`
- **URL**: `ws://localhost:8000/system/health/ws`
- **Events**: `health_update`
- **Returns**: `{ isConnected, health, requestUpdate }`

### `useKillSwitchWebSocket()`
- **URL**: `ws://localhost:8000/emergency/ws`
- **Events**: `kill_switch_update`, `kill_switch_activated`
- **Returns**: `{ isConnected, killSwitch, sendMessage }`

### `usePnLWebSocket()`
- **URL**: `ws://localhost:8000/analytics/pnl/ws`
- **Events**: `pnl_update`
- **Returns**: `{ isConnected, currentPnL, pnlData, sendMessage }`

### `useNotificationsWebSocket()`
- **URL**: `ws://localhost:8000/notifications/ws`
- **Events**: `notification`, `unread_count`
- **Returns**: `{ isConnected, notifications, unreadCount, markAsRead, markAllAsRead }`

---

## 3. ⚠️ Error Handling

### Global Error Types
```typescript
type ApiErrorType = 
  | 'license_required'      // 403 - License/plan required
  | '2fa_required'          // 401 - 2FA verification needed
  | 'circuit_breaker'       // 503 - System overloaded
  | 'rate_limited'          // 429 - Too many requests
  | 'unauthorized'          // 401 - General unauthorized
  | 'server_error';         // 5xx - Server error
```

### Error Interceptors
| HTTP Status | Error Type | Action |
|-------------|------------|--------|
| 403 | `license_required` | Toast + Optional redirect to /pricing |
| 401 (2FA) | `2fa_required` | Toast + Optional redirect to /settings/security |
| 503 | `circuit_breaker` | Toast with retry countdown |
| 429 | `rate_limited` | Toast with wait time |
| 401 | `unauthorized` | Token refresh → Redirect to /login |
| 5xx | `server_error` | Error toast |

### Using Error Handler
```tsx
// In any component
import { useApiErrorHandler } from '@/hooks/use-api-error-handler';

function MyComponent() {
  // Full handler with redirects
  useApiErrorHandler({
    redirectOnLicense: true,
    redirectOn2FA: true,
  });

  // ... rest of component
}

// Or simple toast-only version
import { useApiErrorToast } from '@/hooks/use-api-error-handler';

function AnotherComponent() {
  useApiErrorToast();
  // ...
}
```

---

## 4. 🔐 License Gating

### Using License Provider
```tsx
// App.tsx already includes LicenseProvider
<LicenseProvider>
  {children}
</LicenseProvider>
```

### Using License Hook
```tsx
import { useLicense, useFeatureGate } from '@/hooks/use-license';

function MyComponent() {
  const { plan, isActive, maxBots, canUseCopyTrading } = useLicense();
  
  // Check specific feature
  const { allowed, reason } = useFeatureGate('copy_trading');
  
  if (!allowed) {
    return <UpgradeBanner reason={reason} />;
  }
}
```

### Using License Button
```tsx
import { LicenseButton, LicenseGate, PlanBadge } from '@/components/ui/license-button';

// Button that respects license
<LicenseButton feature="start_bot" onClick={handleStart}>
  Iniciar Robô
</LicenseButton>

// Gate content based on license
<LicenseGate 
  feature="advanced_analytics" 
  fallback={<UpgradePrompt />}
>
  <AdvancedChart />
</LicenseGate>

// Show current plan badge
<PlanBadge />
```

---

## 5. 🚨 Kill Switch Component

### Header Button
```tsx
import { KillSwitchButton } from '@/components/KillSwitchButton';

// Compact version for header
<KillSwitchButton variant="header" />

// Full card version for settings
<KillSwitchButton variant="full" />
```

---

## 6. 📊 System Health Indicator

```tsx
import { SystemHealthIndicator } from '@/components/SystemHealthIndicator';

// Just a colored dot
<SystemHealthIndicator variant="minimal" />

// Dot + text + hover details
<SystemHealthIndicator variant="compact" />

// Full card with all details
<SystemHealthIndicator variant="detailed" />
```

---

## 7. 📁 Files Changed/Created

### New Files
- `src/hooks/use-api-error-handler.ts` - Global API error handling
- `src/hooks/use-license.tsx` - License context and hooks
- `src/components/KillSwitchButton.tsx` - Emergency stop button
- `src/components/SystemHealthIndicator.tsx` - Health status display
- `src/components/ui/license-button.tsx` - License-gated button

### Modified Files
- `src/lib/api.ts` - Added all new API endpoints
- `src/hooks/use-websocket.ts` - Added specialized WebSocket hooks
- `src/pages/Affiliate.tsx` - Replaced mocks with real API
- `src/components/layout/Header.tsx` - Added Kill Switch and Health indicators
- `src/App.tsx` - Added LicenseProvider

---

## 8. ✅ Checklist Status

| Feature | Backend | Frontend | Status |
|---------|---------|----------|--------|
| Kill Switch | `/api/emergency/*` | KillSwitchButton + WebSocket | ✅ Complete |
| Licenses | Middleware | LicenseProvider + LicenseButton | ✅ Complete |
| 2FA | TOTP validation | twoFactorApi + interceptor | ✅ Complete |
| PnL Real | `/audit/pnl/*` | auditApi + usePnLWebSocket | ✅ Complete |
| Exchanges | Encryption | settingsApi + validation feedback | ✅ Complete |
| Error Handling | HTTP codes | Global interceptors + toasts | ✅ Complete |
| Skeletons | N/A | Affiliate + existing components | ✅ Complete |

---

## 9. 🔧 Environment Variables

```env
# Frontend (.env)
VITE_API_BASE=http://localhost:8000

# Backend (.env)
ENCRYPTION_KEY=your-32-byte-key
MONGODB_URL=mongodb://localhost:27017
JWT_SECRET=your-jwt-secret
```

---

## 10. 📝 Usage Examples

### Making API Calls with Error Handling
```tsx
import { auditApi } from '@/lib/api';
import { useApiErrorToast } from '@/hooks/use-api-error-handler';

function PnLChart() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  
  useApiErrorToast(); // Enable global error toasts
  
  useEffect(() => {
    const fetchData = async () => {
      try {
        const history = await auditApi.getPnLHistory('30d');
        setData(history);
      } catch (err) {
        // Error already handled by interceptor
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);
  
  return loading ? <Skeleton /> : <Chart data={data} />;
}
```

### Using Real-time WebSocket Data
```tsx
import { usePnLWebSocket } from '@/hooks/use-websocket';

function RealTimePnL() {
  const { isConnected, currentPnL } = usePnLWebSocket();
  
  return (
    <div>
      <Badge variant={isConnected ? 'default' : 'outline'}>
        {isConnected ? '🟢 Live' : '⚪ Offline'}
      </Badge>
      {currentPnL && (
        <span className={currentPnL.totalPnL >= 0 ? 'text-green-500' : 'text-red-500'}>
          ${currentPnL.totalPnL.toFixed(2)}
        </span>
      )}
    </div>
  );
}
```

---

*Last updated: Session 6 - Frontend-Backend Synchronization*
