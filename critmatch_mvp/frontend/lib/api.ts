import type { MatchRequest, MatchResponse } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function runMatch(payload: MatchRequest): Promise<MatchResponse> {
  const response = await fetch(`${API_BASE_URL}/match`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`CritMatch API error: ${response.status}`);
  }

  return response.json();
}
