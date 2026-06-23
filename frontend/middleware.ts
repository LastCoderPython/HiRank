import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Domains that should permanently redirect to aariv.in
const LEGACY_DOMAINS = ['rankroute.vocoweb.in'];

export function middleware(request: NextRequest) {
  const host = request.headers.get('host') || '';
  // Strip port if present (e.g. rankroute.vocoweb.in:3000 -> rankroute.vocoweb.in)
  const domain = host.split(':')[0];

  if (LEGACY_DOMAINS.includes(domain)) {
    // Preserve the full path and query string in the redirect
    const url = request.nextUrl.clone();
    url.protocol = 'https:';
    url.host = 'aariv.in';

    return NextResponse.redirect(url, {
      status: 301,
      headers: {
        // Tell clients to cache this redirect for 1 year (SEO best practice for permanent moves)
        'Cache-Control': 'public, max-age=31536000, immutable',
      },
    });
  }

  return NextResponse.next();
}

export const config = {
  // Run on all routes except Next.js internals and static files
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
