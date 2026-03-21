import React, { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import {
    Box,
    Chip,
    CircularProgress,
    Typography,
} from '@mui/material'
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid'

const API = 'http://localhost:8000'

interface JournalEntry {
    id: string
    run_id: string
    line_number: number
    company_code: string
    posting_date: string
    document_date: string
    document_type: string
    gl_account: string
    debit: number | null
    credit: number | null
    currency: string
    item_text: string | null
    source_file_name: string | null
    created_at: string | null
    reconciliation_match_id: string | null
    bank_statement_id: string | null
    remittance_advice_line_id: string | null
}

function fmt(n: number | null | undefined, currency?: string | null) {
    if (n == null) return '–'
    const s = n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    return currency ? `${currency} ${s}` : s
}

export default function JournalPage() {
    const [entries, setEntries] = useState<JournalEntry[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        axios
            .get<JournalEntry[]>(`${API}/analytics/journal-entries`)
            .then((r) => setEntries(r.data))
            .finally(() => setLoading(false))
    }, [])

    const columns = useMemo<GridColDef[]>(() => [
        { field: 'line_number', headerName: '#', width: 70 },
        { field: 'company_code', headerName: 'Company', width: 120 },
        { field: 'posting_date', headerName: 'Posting Date', width: 130 },
        { field: 'document_date', headerName: 'Doc Date', width: 120 },
        { field: 'document_type', headerName: 'Doc Type', width: 110 },
        { field: 'gl_account', headerName: 'GL Account', width: 130 },
        {
            field: 'debit',
            headerName: 'Debit',
            width: 120,
            valueGetter: (_v, row) => fmt(row.debit),
        },
        {
            field: 'credit',
            headerName: 'Credit',
            width: 120,
            valueGetter: (_v, row) => fmt(row.credit),
        },
        { field: 'currency', headerName: 'Ccy', width: 80 },
        { field: 'item_text', headerName: 'Item Text', minWidth: 220, flex: 1, valueGetter: (_v, row) => row.item_text ?? '–' },
        { field: 'source_file_name', headerName: 'Source File', minWidth: 170, flex: 1, valueGetter: (_v, row) => row.source_file_name ?? '–' },
        {
            field: 'links',
            headerName: 'Links',
            width: 220,
            sortable: false,
            filterable: false,
            renderCell: (params: GridRenderCellParams<JournalEntry>) => (
                <Box display='flex' gap={0.5} flexWrap='wrap'>
                    {params.row.reconciliation_match_id && (
                        <Chip size='small' label='Match' color='success' variant='outlined' />
                    )}
                    {params.row.bank_statement_id && (
                        <Chip size='small' label='Bank' color='primary' variant='outlined' />
                    )}
                    {params.row.remittance_advice_line_id && (
                        <Chip size='small' label='Rem.' color='secondary' variant='outlined' />
                    )}
                </Box>
            ),
        },
    ], [])

    if (loading) {
        return (
            <Box display='flex' justifyContent='center' alignItems='center' minHeight={300}>
                <CircularProgress />
            </Box>
        )
    }

    return (
        <Box sx={{ p: 3 }}>
            <Typography variant='h5' gutterBottom>
                Journal Entries
            </Typography>
            <DataGrid
                rows={entries}
                columns={columns}
                autoHeight
                disableRowSelectionOnClick
                pageSizeOptions={[10, 25, 50]}
                initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
            />
        </Box>
    )
}
