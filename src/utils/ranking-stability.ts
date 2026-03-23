/**
 * Deterministic Ranking with 20-Day Seed
 * 
 * Ensures strategy rankings remain stable for 20 days,
 * preventing visual "flicker" from daily updates.
 * 
 * Algorithm:
 * 1. Calculate 20-day window: Math.floor(Date.now() / (20 * 24 * 60 * 60 * 1000))
 * 2. Seed deterministic shuffle with window
 * 3. Apply to ranking list
 * 
 * This ensures:
 * - Same ranking for all users during 20-day period
 * - Rankings change predictably every 20 days
 * - No visual "dancing" of positions mid-week
 */

/**
 * Get the current 20-day window index
 * @returns: Window number since epoch (changes every 20 days)
 */
export function get20DayWindow(): number {
  const TWENTY_DAYS_MS = 20 * 24 * 60 * 60 * 1000; // 1,728,000,000 ms
  return Math.floor(Date.now() / TWENTY_DAYS_MS);
}

/**
 * Deterministic shuffle using 20-day seed
 * Uses Fisher-Yates algorithm with time-based seed for deterministic results
 */
export function shuffle20DayDeterministic<T>(array: T[]): T[] {
  const arr = [...array];
  const seed = get20DayWindow();
  
  // Pseudo-random generator with seed
  // (Linear Congruential Generator)
  let seededRandom = (index: number): number => {
    const x = Math.sin(seed + index) * 10000;
    return x - Math.floor(x);
  };
  
  // Fisher-Yates shuffle with seeded RNG
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(seededRandom(i) * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  
  return arr;
}

/**
 * Sort strategies with 20-day deterministic stable ordering
 * Maintains position stability during 20-day window
 */
export function rankStrategiesWithStability<
  T extends { id?: string | number; name?: string; [key: string]: any }
>(
  strategies: T[],
  compareFn?: (a: T, b: T) => number
): T[] {
  // First, sort by profit/metric if provided
  let sorted = [...strategies];
  if (compareFn) {
    sorted.sort(compareFn);
  }
  
  // Group by equal values (stable within groups)
  const grouped: T[][] = [];
  let currentGroup: T[] = [];
  let lastValue: any = null;
  
  for (let i = 0; i < sorted.length; i++) {
    const value = compareFn ? compareFn(sorted[i], sorted[i + 1] || sorted[i]) : 0;
    
    if (i === 0 || lastValue === value) {
      currentGroup.push(sorted[i]);
    } else {
      if (currentGroup.length > 0) {
        grouped.push(currentGroup);
      }
      currentGroup = [sorted[i]];
      lastValue = value;
    }
  }
  if (currentGroup.length > 0) {
    grouped.push(currentGroup);
  }
  
  // Shuffle within groups using 20-day seed
  const result: T[] = [];
  for (const group of grouped) {
    if (group.length > 1) {
      const shuffled = shuffle20DayDeterministic(group);
      result.push(...shuffled);
    } else {
      result.push(...group);
    }
  }
  
  return result;
}

/**
 * Format ranking info for display
 * Shows which 20-day window we're in and when it resets
 */
export function getRankingWindowInfo(): {
  windowNumber: number;
  startDate: Date;
  endDate: Date;
  daysRemaining: number;
  percentageIntoWindow: number;
} {
  const TWENTY_DAYS_MS = 20 * 24 * 60 * 60 * 1000;
  const currentWindow = get20DayWindow();
  const startTimeMs = currentWindow * TWENTY_DAYS_MS;
  const startDate = new Date(startTimeMs);
  const endDate = new Date(startTimeMs + TWENTY_DAYS_MS);
  
  const now = Date.now();
  const daysRemaining = Math.ceil((endDate.getTime() - now) / (24 * 60 * 60 * 1000));
  const percentageIntoWindow = ((now - startTimeMs) / TWENTY_DAYS_MS) * 100;
  
  return {
    windowNumber: currentWindow,
    startDate,
    endDate,
    daysRemaining,
    percentageIntoWindow,
  };
}
