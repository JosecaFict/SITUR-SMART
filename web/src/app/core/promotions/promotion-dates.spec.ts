import { fromBoliviaInput, toBoliviaInput } from './promotion-dates';

describe('horarios de promoción en Bolivia', () => {
  it('mantiene el día y la hora local aunque el navegador use otra zona', () => {
    expect(toBoliviaInput('2026-11-01T01:30:00Z')).toBe('2026-10-31T21:30');
    expect(fromBoliviaInput('2026-10-31T21:30')).toBe('2026-10-31T21:30:00-04:00');
  });
});
