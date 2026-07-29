import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Typography,
} from '@mui/material';
import type { ReactNode } from 'react';

interface AdvancedSectionProps {
  children: ReactNode;
  description?: string;
}

export function AdvancedSection({
  children,
  description = 'These settings are intended for uncommon or specialist configurations.',
}: AdvancedSectionProps) {
  return (
    <Accordion disableGutters variant="outlined">
      <AccordionSummary>
        <Typography sx={{ fontWeight: 600 }}>Advanced</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Alert severity="warning" sx={{ mb: 2 }}>
          {description}
        </Alert>
        {children}
      </AccordionDetails>
    </Accordion>
  );
}
