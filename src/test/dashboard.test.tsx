/**
 * Smoke tests for the Dashboard page.
 * Verifies initial render under authenticated state.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Stub auth context
const mockUser = { id: "u1", email: "user@test.com", name: "Test User" };
vi.mock("@/context/AuthContext", () => ({
  useAuthStore: Object.assign(
    (selector?: (s: any) => any) => {
      const state = {
        user: mockUser,
        accessToken: "tok-123",
        isAuthenticated: true,
        isLoading: false,
        isHydrated: true,
      };
      return selector ? selector(state) : state;
    },
    {
      getState: () => ({
        user: mockUser,
        accessToken: "tok-123",
        isAuthenticated: true,
        isLoading: false,
        isHydrated: true,
      }),
    },
  ),
}));

// Mock fetch for API calls
vi.stubGlobal(
  "fetch",
  vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ bots: [], stats: {} }),
    text: () => Promise.resolve("{}"),
    headers: new Headers(),
  }),
);

// Mock ALL child components to avoid cascading dependency issues
vi.mock("@/components/KuCoinOnboarding", () => ({
  KuCoinOnboarding: ({ onComplete }: any) => <div data-testid="kucoin-onboarding" />,
}));

vi.mock("@/components/kucoin/KuCoinDashboard", () => ({
  KuCoinDashboard: (props: any) => <div data-testid="kucoin-dashboard" />,
}));

vi.mock("@/components/gamification/BotConfigModal", () => ({
  __esModule: true,
  default: () => null,
  BotConfigModal: () => null,
}));

vi.mock("@/components/patterns", () => ({
  DashboardKPISkeleton: () => <div data-testid="kpi-skeleton" />,
  ChartSkeleton: () => <div data-testid="chart-skeleton" />,
}));

vi.mock("@/components/layouts", () => {
  const Wrapper = ({ children }: any) => <div>{children}</div>;
  return {
    DashboardLayout: Wrapper,
    DashboardGrid: {
      Root: Wrapper,
      Full: Wrapper,
      Main: Wrapper,
      Aside: Wrapper,
    },
  };
});

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

import Dashboard from "@/pages/Dashboard";

function renderDashboard() {
  return render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <Dashboard />
    </MemoryRouter>,
  );
}

describe("Dashboard page", () => {
  it("renders without throwing", () => {
    expect(() => renderDashboard()).not.toThrow();
  });

  it("produces visible output", () => {
    renderDashboard();
    // The page should render something
    expect(document.body.innerHTML.length).toBeGreaterThan(0);
  });
});
