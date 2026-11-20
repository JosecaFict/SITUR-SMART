/** Mensaje al publicar una promoción: cuántos turistas interesados recibieron el aviso. */
export function publishedMessage(notified: number | undefined): string {
  if (!notified) return 'Promoción publicada. Todavía ningún turista tiene intereses que coincidan.';
  return `Promoción publicada. Se notificó a ${notified} ${notified === 1 ? 'turista interesado' : 'turistas interesados'}.`;
}