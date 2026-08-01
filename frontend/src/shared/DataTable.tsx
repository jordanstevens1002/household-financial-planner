import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import type { ReactNode } from 'react';

export interface DataColumn<Row> {
  key: string;
  label: string;
  render: (row: Row) => ReactNode;
}

interface DataTableProps<Row> {
  caption: string;
  columns: DataColumn<Row>[];
  getRowKey: (row: Row) => string;
  rows: Row[];
}

export function DataTable<Row>({
  caption,
  columns,
  getRowKey,
  rows,
}: DataTableProps<Row>) {
  return (
    <TableContainer component={Paper} variant="outlined">
      <Table aria-label={caption}>
        <TableHead>
          <TableRow>
            {columns.map((column) => (
              <TableCell key={column.key}>{column.label}</TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={getRowKey(row)}>
              {columns.map((column) => (
                <TableCell key={column.key}>{column.render(row)}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
