/**
 * Integration-level tests for the Settings page.
 * Verifies that tabs render and basic interactions work.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Mock heavy dependencies before import
vi.mock("@/services/userService", () => ({
  userService: {
    getProfile: vi.fn().mockResolvedValue({
      id: "u1",
      email: "user@test.com",
      name: "Test User",
      avatar_url: null,
    }),
    updateProfile: vi.fn().mockResolvedValue({ success: true }),
    getAvailableAvatars: vi.fn().mockResolvedValue([]),
    getAvatarById: vi.fn().mockReturnValue(null),
  },
}));

vi.mock("@/services/exchangeService", () => ({
  exchangeService: {
    getCredential: vi.fn().mockResolvedValue(null),
    saveCredentials: vi.fn().mockResolvedValue({ success: true }),
  },
  ExchangeCredentialInfo: class {},
}));

vi.mock("@/services/apiClient", () => ({
  apiCall: vi.fn().mockResolvedValue({ ok: true, json: () => ({}) }),
}));

vi.mock("@/hooks/use-language", () => ({
  useLanguage: () => ({
    language: "pt",
    setLanguage: vi.fn(),
    availableLanguages: [
      { code: "pt", name: "Português" },
      { code: "en", name: "English" },
    ],
    t: (key: string) => key,
  }),
}));

vi.mock("@/context/AuthContext", () => ({
  useAuthStore: Object.assign(
    (selector?: (s: any) => any) => {
      const state = {
        user: { id: "u1", email: "user@test.com", name: "Test User" },
        accessToken: "tok-123",
        isAuthenticated: true,
      };
      return selector ? selector(state) : state;
    },
    {
      getState: () => ({
        user: { id: "u1", email: "user@test.com", name: "Test User" },
        accessToken: "tok-123",
        isAuthenticated: true,
      }),
    },
  ),
}));

vi.mock("@/components/NotificationSettings", () => ({
  NotificationSettings: () => <div data-testid="notification-settings" />,
}));

vi.mock("@/components/PriceAlertManager", () => ({
  PriceAlertManager: () => <div data-testid="price-alert-manager" />,
}));

vi.mock("@/components/AvatarSelectorModal", () => ({
  AvatarSelectorModal: () => null,
}));

vi.mock("@/components/LanguageSelector", () => ({
  LanguageSelector: () => <div data-testid="language-selector" />,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

import Settings from "@/pages/Settings";

function renderSettings(tab?: string) {
  const route = tab ? `/settings?tab=${tab}` : "/settings";
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Settings />
    </MemoryRouter>,
  );
}

describe("Settings page", () => {
  it("renders without crashing", () => {
    renderSettings();
    expect(document.body.textContent).toBeTruthy();
  });

  it("renders profile tab triggers", async () => {
    renderSettings("profile");
    // t() returns key as-is, and tab renders twice (desktop + mobile spans)
    const elements = await screen.findAllByText(/settings\.profile/i);
    expect(elements.length).toBeGreaterThan(0);
  });

  it("renders security tab trigger", async () => {
    renderSettings("security");
    const elements = await screen.findAllByText(/settings\.security/i);
    expect(elements.length).toBeGreaterThan(0);
  });

  it("renders privacy tab trigger", async () => {
    renderSettings("privacy");
    // Privacy tab uses hardcoded "Privacidade" / "LGPD"
    const elements = await screen.findAllByText(/privacidade|lgpd/i);
    expect(elements.length).toBeGreaterThan(0);
  });
});
