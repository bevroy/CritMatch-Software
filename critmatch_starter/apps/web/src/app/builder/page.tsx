import { redirect } from "next/navigation";

export default async function BuilderRedirect({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined) continue;
    if (Array.isArray(v)) v.forEach((x) => qs.append(k, x));
    else qs.set(k, v);
  }
  const suffix = qs.toString();
  redirect(suffix ? `/cohort?${suffix}` : "/cohort");
}
