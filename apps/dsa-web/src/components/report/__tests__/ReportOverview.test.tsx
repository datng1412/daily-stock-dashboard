import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReportOverview } from '../ReportOverview';

const baseMeta = {
  queryId: 'q-1',
  stockCode: '600519',
  stockName: 'Kweichow Moutai',
  reportType: 'detailed' as const,
  reportLanguage: 'zh' as const,
  createdAt: '2026-03-21T08:00:00Z',
};

const baseSummary = {
  analysisSummary: 'Trend remains strong',
  operationAdvice: 'Continue monitoring signal quality',
  trendPrediction: 'Short-term range remains firm',
  sentimentScore: 78,
};

describe('ReportOverview', () => {
  it('renders related boards with leading and lagging markers', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [
            { name: ' Baijiu ', type: 'Industry' },
            { name: 'Consumer', type: 'Concept' },
            { name: 'New energy' },
          ],
          sectorRankings: {
            top: [{ name: 'Baijiu', changePct: 2.31 }],
            bottom: [{ name: 'Consumer', changePct: -1.2 }],
          },
        }}
      />,
    );

    expect(screen.getByText('Related sectors')).toBeInTheDocument();
    expect(screen.getByText('Baijiu')).toBeInTheDocument();
    expect(screen.getByText('Industry')).toBeInTheDocument();
    expect(screen.getByText('Leading')).toBeInTheDocument();
    expect(screen.getByText('+2.31%')).toBeInTheDocument();
    expect(screen.getByText('Lagging')).toBeInTheDocument();
    expect(screen.getByText('-1.20%')).toBeInTheDocument();
    expect(screen.queryByText('Neutral')).not.toBeInTheDocument();
  });

  it('places related boards below action advice and renders more than three on one row', () => {
    const { container } = render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [
            { name: 'Baijiu', type: 'Industry' },
            { name: 'Consumer', type: 'Concept' },
            { name: 'High-end manufacturing' },
            { name: 'Shanghai Stock Connect' },
          ],
        }}
      />,
    );

    const actionAdviceTitle = screen.getByText('Action notes');
    const relatedBoardsRegion = screen.getByRole('region', { name: 'Related sectors' });
    const boardList = container.querySelector('.home-related-board-list');

    expect(actionAdviceTitle.compareDocumentPosition(relatedBoardsRegion) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText('Shanghai Stock Connect')).toBeInTheDocument();
    expect(boardList).toHaveClass('flex-nowrap', 'overflow-x-auto');
  });

  it('shows board list when rankings are unavailable', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: 'Semiconductor', type: 'Industry' }],
        }}
      />,
    );

    expect(screen.getByText('Related sectors')).toBeInTheDocument();
    expect(screen.getByText('Semiconductor')).toBeInTheDocument();
    expect(screen.queryByText('Neutral')).not.toBeInTheDocument();
    expect(screen.queryByText('Leading')).not.toBeInTheDocument();
    expect(screen.queryByText('Lagging')).not.toBeInTheDocument();
  });

  it('hides related boards section when no boards are available', () => {
    render(<ReportOverview meta={baseMeta} summary={baseSummary} details={{ belongBoards: [] }} />);

    expect(screen.queryByText('Related sectors')).not.toBeInTheDocument();
  });

  it('fails open on malformed ranking payloads', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: ' Baijiu ' }],
          sectorRankings: {
            top: {} as unknown as never[],
            bottom: [{ name: 'Baijiu', changePct: '-2.5%' as unknown as number }],
          },
        }}
      />,
    );

    expect(screen.getByText('Related sectors')).toBeInTheDocument();
    expect(screen.getByText('Baijiu')).toBeInTheDocument();
    expect(screen.getByText('Lagging')).toBeInTheDocument();
    expect(screen.getByText('-2.50%')).toBeInTheDocument();
  });
});
