import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import { MobileSidebar } from '@/components/layout/MobileSidebar';
import { OperationDetailModal } from '@/components/modals/OperationDetailModal';
import { RobotConfigModal } from '@/components/robots/RobotConfigModal';

describe('Responsive / UI components', () => {
  it('renders MobileSidebar links when open', () => {
    const onOpenChange = vi.fn();
    render(
      <MemoryRouter>
        <MobileSidebar open={true} onOpenChange={onOpenChange} />
      </MemoryRouter>
    );

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Robôs')).toBeInTheDocument();
  });

  it('OperationDetailModal shows operation data when open', () => {
    const operation = {
      id: 'op1',
      pair: 'BTC/USDT',
      type: 'buy' as const,
      amount: 0.5,
      price: 20000,
      entryPrice: 20000,
      exitPrice: 21000,
      profit: 500,
      date: '2026-01-01',
      duration: '2h',
      robot: 'TestBot',
      fees: 0.0001,
      notes: 'Test note',
    };

    render(
      <OperationDetailModal open={true} onOpenChange={vi.fn()} operation={operation} />
    );

    expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
    expect(screen.getByText('Resultado')).toBeInTheDocument();
    expect(screen.getByText('TestBot')).toBeInTheDocument();
    expect(screen.getByText('Test note')).toBeInTheDocument();
  });

  it('RobotConfigModal renders form controls when open', () => {
    const onClose = vi.fn();
    render(<RobotConfigModal isOpen={true} onClose={onClose} />);

    expect(screen.getByText('Par de negociação')).toBeInTheDocument();
    expect(screen.getByText('Salvar Configurações')).toBeInTheDocument();
  });

  it('does not crash when resizing viewport and rendering components', () => {
    // mobile
    (window as any).innerWidth = 375;
    fireEvent(window, new Event('resize'));

    render(
      <MemoryRouter>
        <MobileSidebar open={true} onOpenChange={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.getByText('Dashboard')).toBeInTheDocument();

    // desktop
    (window as any).innerWidth = 1024;
    fireEvent(window, new Event('resize'));

    // rendering modals at desktop size
    const operation = {
      id: 'op2',
      pair: 'ETH/USDT',
      type: 'sell' as const,
      amount: 1,
      price: 1500,
      entryPrice: 1500,
      exitPrice: 1400,
      profit: -100,
      date: '2026-01-02',
      duration: '1h',
      robot: 'Bot2',
      fees: 0.0002,
    };

    render(<OperationDetailModal open={true} onOpenChange={vi.fn()} operation={operation} />);

    expect(screen.getByText('ETH/USDT')).toBeInTheDocument();
  });
});
