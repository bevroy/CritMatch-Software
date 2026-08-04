import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PREFIXES = ["/login", "/launch", "/auth/callback", "/_next", "/api"];

function isPublicPath(pathname: string): boolean {
  if (pathname === "/") return true;
  if (PUBLIC_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(prefix + "/"))) {
    return true;
  }
  // Static assets (for example /logo.png, /manifest.webmanifest)
  if (/\.[a-zA-Z0-9]+$/.test(pathname)) {
    return true;
  }
  return false;
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  const cookieName = process.env.SESSION_COOKIE_NAME || "critmatch_session";
  const sessionCookie = request.cookies.get(cookieName)?.value;
  if (sessionCookie) {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  url.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/:path*"],
};
