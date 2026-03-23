/**
 * Unit tests for the Zustand auth store.
 *
 * We test state transitions (setUser, setTokens, logout, clearError)
 * without hitting any real network — fetch is mocked globally.
 */
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";

// Reset modules between tests so Zustand starts fresh
let useAuthStore: typeof import("@/context/AuthContext").useAuthStore;

beforeEach(async () => {
  // Clear persisted data
  localStorage.clear();
  sessionStorage.clear();

  // Reset module cache so Zustand creates a new store instance
  vi.resetModules();
  const mod = await import("@/context/AuthContext");
  useAuthStore = mod.useAuthStore;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AuthStore — initial state", () => {
  it("starts unauthenticated", () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(state.isAuthenticated).toBe(false);
  });

  it("has no error initially", () => {
    expect(useAuthStore.getState().error).toBeNull();
  });
});

describe("AuthStore — setUser / setTokens", () => {
  it("setUser updates user and isAuthenticated", () => {
    const user = { id: "u1", email: "a@b.com", name: "Alice" };
    useAuthStore.getState().setUser(user);
    const state = useAuthStore.getState();
    expect(state.user).toEqual(user);
    expect(state.isAuthenticated).toBe(true);
  });

  it("setUser(null) clears auth", () => {
    useAuthStore.getState().setUser({ id: "u1", email: "a@b.com", name: "X" });
    useAuthStore.getState().setUser(null);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("setTokens stores access token", () => {
    useAuthStore.getState().setTokens("tok123", "ref123");
    expect(useAuthStore.getState().accessToken).toBe("tok123");
  });
});

describe("AuthStore — logout", () => {
  it("clears user, tokens, and auth flag", () => {
    // Prevent real fetch
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));

    useAuthStore.getState().setUser({ id: "1", email: "a@b.com", name: "A" });
    useAuthStore.getState().setTokens("tok", "ref");
    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(state.isAuthenticated).toBe(false);
  });
});

describe("AuthStore — clearError", () => {
  it("resets error to null", () => {
    // Internally set an error by triggering a failed login
    const store = useAuthStore.getState();
    // Directly poke internal state via setState (Zustand exposes it)
    useAuthStore.setState({ error: "something went wrong" });
    expect(useAuthStore.getState().error).toBe("something went wrong");

    useAuthStore.getState().clearError();
    expect(useAuthStore.getState().error).toBeNull();
  });
});

describe("AuthStore — login", () => {
  it("sets user and token on successful login", async () => {
    const responseBody = JSON.stringify({
      success: true,
      access_token: "jwt-tok-123",
      user: { id: "u1", email: "a@b.com", name: "Alice" },
    });
    const fakeResponse = {
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(JSON.parse(responseBody)),
      text: vi.fn().mockResolvedValue(responseBody),
      headers: new Headers({ "content-type": "application/json" }),
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeResponse));

    await useAuthStore.getState().login("a@b.com", "StrongP@ss1");

    const state = useAuthStore.getState();
    expect(state.user).toEqual({ id: "u1", email: "a@b.com", name: "Alice" });
    expect(state.accessToken).toBe("jwt-tok-123");
    expect(state.isAuthenticated).toBe(true);
    expect(state.error).toBeNull();
  });

  it("sets error on failed login", async () => {
    const fakeResponse = {
      ok: false,
      status: 401,
      json: vi.fn().mockResolvedValue({ detail: "Invalid credentials" }),
      text: vi.fn().mockResolvedValue("Invalid credentials"),
      headers: new Headers(),
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeResponse));

    try {
      await useAuthStore.getState().login("bad@b.com", "wrong");
    } catch {
      // login throws on failure
    }

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.error).toBeTruthy();
  });
});
