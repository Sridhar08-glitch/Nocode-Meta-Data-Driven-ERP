/**
 * Workspace brand mark — renders WorkspaceBranding.logo_url + app_name. Pure/presentational so it can
 * be fed from TenantContext (in-app) OR the pre-auth branding snapshot (login). One render, no duplicate
 * branding logic. Falls back to the product name when a workspace has set none.
 */
export function BrandMark({
  logoUrl,
  appName,
  className = "",
  size = 24,
}: {
  logoUrl?: string;
  appName?: string;
  className?: string;
  size?: number;
}) {
  const name = appName?.trim() || "Sridhar ERP";
  return (
    <span className={`flex items-center gap-2 font-heading font-semibold ${className}`}>
      {logoUrl ? (
        // eslint-disable-next-line @next/next/no-img-element -- runtime workspace logo URL (not build-time)
        <img
          src={logoUrl}
          alt={name}
          height={size}
          style={{ height: size, maxWidth: size * 5 }}
          className="w-auto object-contain"
        />
      ) : (
        <span className="truncate">{name}</span>
      )}
    </span>
  );
}
