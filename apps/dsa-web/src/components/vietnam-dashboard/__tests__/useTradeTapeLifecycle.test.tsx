import { StrictMode, type ReactNode } from 'react';
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  resolveTradeTapeLifecycleState,
  tradeTapeLifecycleDetail,
  useTradeTapeLifecycle,
  type UseTradeTapeLifecycleOptions,
} from '../useTradeTapeLifecycle';

const unresolvedOptions = (
  overrides: Partial<UseTradeTapeLifecycleOptions> = {},
): UseTradeTapeLifecycleOptions => ({
  symbol: 'FPT',
  generation: 1,
  hasRows: false,
  status: 'loading',
  pendingEvidence: true,
  requestLoading: false,
  ...overrides,
});

describe('trade tape lifecycle state', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-28T02:00:00Z'));
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('keeps one unresolved lifecycle loading through 19 seconds', () => {
    const { result } = renderHook(() => useTradeTapeLifecycle(unresolvedOptions()));

    expect(result.current.state).toBe('loading');
    act(() => vi.advanceTimersByTime(19_000));
    expect(result.current.state).toBe('loading');
  });

  it('transitions an unresolved completed lifecycle at 20 seconds and remains terminal at 21 and 61 seconds', () => {
    const { result } = renderHook(() => useTradeTapeLifecycle(unresolvedOptions()));

    act(() => vi.advanceTimersByTime(20_000));
    expect(result.current.state).toBe('no_data');
    act(() => vi.advanceTimersByTime(1_000));
    expect(result.current.state).toBe('no_data');
    act(() => vi.advanceTimersByTime(40_000));
    expect(result.current.state).toBe('no_data');
  });

  it('does not let four-second startup polling reset the deadline', () => {
    const onStartupPoll = vi.fn();
    const { result } = renderHook(() => useTradeTapeLifecycle(unresolvedOptions({ onStartupPoll })));

    act(() => vi.advanceTimersByTime(20_000));

    expect(result.current.state).toBe('no_data');
    expect(onStartupPoll).toHaveBeenCalledTimes(4);
  });

  it.each([
    ['unavailable', 'unavailable'],
    ['disabled', 'disabled'],
    ['error', 'error'],
  ] as const)('gives typed %s precedence over request loading', (status, expected) => {
    expect(resolveTradeTapeLifecycleState({
      hasRows: false,
      status,
      requestLoading: true,
    })).toBe(expected);
  });

  it('does not return a typed terminal state to loading on a later in-flight poll', () => {
    const { result, rerender } = renderHook(
      (options: UseTradeTapeLifecycleOptions) => useTradeTapeLifecycle(options),
      { initialProps: unresolvedOptions({ status: 'unavailable' }) },
    );

    expect(result.current.state).toBe('unavailable');
    rerender(unresolvedOptions({ status: 'unavailable', requestLoading: true }));
    expect(result.current.state).toBe('unavailable');
  });

  it('starts a fresh deadline when the ticker changes', () => {
    const { result, rerender } = renderHook(
      (options: UseTradeTapeLifecycleOptions) => useTradeTapeLifecycle(options),
      { initialProps: unresolvedOptions() },
    );
    act(() => vi.advanceTimersByTime(20_000));
    expect(result.current.state).toBe('no_data');

    rerender(unresolvedOptions({ symbol: 'SSI' }));
    expect(result.current.state).toBe('loading');
    act(() => vi.advanceTimersByTime(19_000));
    expect(result.current.state).toBe('loading');
    act(() => vi.advanceTimersByTime(1_000));
    expect(result.current.state).toBe('no_data');
  });

  it('starts a fresh deadline for a new subscription generation', () => {
    const { result, rerender } = renderHook(
      (options: UseTradeTapeLifecycleOptions) => useTradeTapeLifecycle(options),
      { initialProps: unresolvedOptions() },
    );
    act(() => vi.advanceTimersByTime(20_000));

    rerender(unresolvedOptions({ generation: 2 }));
    expect(result.current.state).toBe('loading');
  });

  it('preserves the original deadline for the same ticker and generation', () => {
    const { result, rerender } = renderHook(
      (options: UseTradeTapeLifecycleOptions) => useTradeTapeLifecycle(options),
      { initialProps: unresolvedOptions() },
    );
    act(() => vi.advanceTimersByTime(19_000));
    rerender(unresolvedOptions({ requestLoading: true }));
    act(() => vi.advanceTimersByTime(1_000));

    expect(result.current.state).toBe('unavailable');
    expect(result.current.deadlineExpired).toBe(true);
  });

  it('transitions usable rows to ready', () => {
    expect(resolveTradeTapeLifecycleState({ hasRows: true, status: 'ok' })).toBe('ready');
  });

  it('keeps usable rows visible as reconnecting during refresh', () => {
    expect(resolveTradeTapeLifecycleState({
      hasRows: true,
      status: 'ok',
      requestLoading: true,
    })).toBe('reconnecting');
    expect(tradeTapeLifecycleDetail('reconnecting', 3)).toBe('Refreshing; showing last known trades');
  });

  it('keeps usable rows stale after refresh failure', () => {
    expect(resolveTradeTapeLifecycleState({
      hasRows: true,
      status: 'unavailable',
      requestError: 'provider unavailable',
    })).toBe('stale');
    expect(tradeTapeLifecycleDetail('stale', 3)).toBe('Showing last known trades');
  });

  it('maps a completed empty response to no data', () => {
    expect(resolveTradeTapeLifecycleState({
      hasRows: false,
      status: 'ok',
      requestLoading: false,
    })).toBe('no_data');
    expect(tradeTapeLifecycleDetail('no_data', 0)).toBe('No trades received');
  });

  it('maps recovering stream evidence without rows to reconnecting', () => {
    expect(resolveTradeTapeLifecycleState({
      hasRows: false,
      status: 'loading',
      streamState: 'recovering',
      requestLoading: true,
    })).toBe('reconnecting');
  });

  it('does not reset the deadline for display-only rerenders', () => {
    const { result, rerender } = renderHook(
      ({ display }: { display: boolean }) => {
        void display;
        return useTradeTapeLifecycle(unresolvedOptions());
      },
      { initialProps: { display: false } },
    );
    act(() => vi.advanceTimersByTime(19_000));
    rerender({ display: true });
    act(() => vi.advanceTimersByTime(1_000));

    expect(result.current.state).toBe('no_data');
  });

  it('does not duplicate the logical poll timer during StrictMode replay', () => {
    const onStartupPoll = vi.fn();
    const wrapper = ({ children }: { children: ReactNode }) => <StrictMode>{children}</StrictMode>;
    renderHook(
      () => useTradeTapeLifecycle(unresolvedOptions({ onStartupPoll })),
      { wrapper },
    );

    act(() => vi.advanceTimersByTime(4_000));
    expect(onStartupPoll).toHaveBeenCalledTimes(1);
  });

  it('clears owned deadline and poll timers on unmount', () => {
    const { unmount } = renderHook(() => useTradeTapeLifecycle(unresolvedOptions({
      onStartupPoll: vi.fn(),
    })));
    expect(vi.getTimerCount()).toBe(2);

    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('stops startup requests after the lifecycle becomes terminal', () => {
    const onStartupPoll = vi.fn();
    const { rerender } = renderHook(
      (options: UseTradeTapeLifecycleOptions) => useTradeTapeLifecycle(options),
      { initialProps: unresolvedOptions({ onStartupPoll }) },
    );
    act(() => vi.advanceTimersByTime(4_000));
    expect(onStartupPoll).toHaveBeenCalledTimes(1);

    rerender(unresolvedOptions({ status: 'unavailable', onStartupPoll }));
    act(() => vi.advanceTimersByTime(20_000));
    expect(onStartupPoll).toHaveBeenCalledTimes(1);
  });
});
