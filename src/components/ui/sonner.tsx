import { Toaster as Sonner, toast } from "sonner";

type ToasterProps = React.ComponentProps<typeof Sonner>;

/**
 * Toaster — design-system styled Sonner wrapper
 *
 * Estilos hardcoded com tokens do design-system (sem CSS vars) para garantir
 * consistência independente do contexto de renderização.
 * Posição padrão: bottom-right. Duração padrão: 4000ms.
 *
 * ATENÇÃO: use notify.ts ao invés de toast() diretamente.
 */
const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="dark"
      position="bottom-right"
      duration={4000}
      gap={8}
      toastOptions={{
        style: {
          // surface.raised
          background:   '#0A1120',
          // content.primary
          color:        '#F1F5F9',
          border:       '1px solid rgba(148,163,184,0.15)',
          borderRadius: '10px',
          fontSize:     '14px',
          fontFamily:   'Inter, sans-serif',
          padding:      '14px 16px',
          boxShadow:    '0 4px 24px rgba(0,0,0,0.40)',
        },
        classNames: {
          description: 'text-[13px] !text-slate-400 mt-0.5',
          actionButton:
            '!bg-brand-primary/15 !text-brand-primary !border !border-brand-primary/25 ' +
            '!text-[12px] !font-medium !rounded-md !px-3 !py-1.5 hover:!bg-brand-primary/25',
          cancelButton:
            '!bg-transparent !text-content-tertiary !text-[12px] hover:!text-content-secondary',
        },
      }}
      {...props}
    />
  );
};

export { Toaster, toast };
