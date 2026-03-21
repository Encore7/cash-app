import React, { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import {
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Grid,
    Paper,
    Tab,
    Tabs,
    Typography,
} from '@mui/material'
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import { PieChart } from '@mui/x-charts/PieChart'

const API = 'http://localhost:8000'

interface TenantSummary {
    id: string
    code: string
    name: string
    is_active: boolean
    matched: number
    unmatched: number
    manual_review: number
    total: number
}

interface Summary {
    matched: number
    unmatched: number
    manual_review: number
    total: number
    tenants: TenantSummary[]
}

interface Match {
    id: string
    run_id: string
    status: string
    confidence_score: number
    match_rule: string
    amount_applied: number | null
    variance_amount: number | null
    notes: string | null
    source: string
    is_selected: boolean
    created_at: string | null
    bank_booking_date: string | null
    bank_amount: number | null
    bank_currency: string | null
    bank_counterparty: string | null
    bank_reference: string | null
    bank_payment_purpose: string | null
    remittance_invoice_number: string | null
    remittance_paid_amount: number | null
    remittance_currency: string | null
    remittance_customer_reference: string | null
}

interface BankStatement {
    id: string
    line_number: number
    booking_date: string
    value_date: string | null
    amount: number
    currency: string
    counterparty_name: string | null
    payment_purpose: string | null
    bank_reference: string | null
    customer_reference: string | null
}

interface RemittanceLine {
    id: string
    line_number: number
    invoice_number: string | null
    invoice_date: string | null
    paid_amount: number | null
    currency: string | null
    customer_reference: string | null
    raw_line_text: string
}

interface RemittanceHeader {
    id: string
    advice_number: string | null
    advice_date: string | null
    payer_name: string | null
    document_currency: string | null
    total_paid_amount: number | null
    lines: RemittanceLine[]
}

const STATUS_COLORS: Record<string, 'success' | 'error' | 'warning' | 'default'> = {
    AUTO_MATCHED: 'success',
    APPROVED: 'success',
    CLOSED: 'success',
    UNMATCHED: 'error',
    MANUAL_REVIEW: 'warning',
    PARTIAL_MATCH: 'warning',
    REJECTED: 'error',
}

function fmt(n: number | null | undefined, currency?: string | null) {
    if (n == null) return '–'
    const s = n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    return currency ? `${currency} ${s}` : s
}

export default function AnalyticsPage() {
    const [summary, setSummary] = useState<Summary | null>(null)
    const [matches, setMatches] = useState<Match[]>([])
    const [bankStmts, setBankStmts] = useState<BankStatement[]>([])
    const [remHeaders, setRemHeaders] = useState<RemittanceHeader[]>([])
    const [matchFilter, setMatchFilter] = useState<string | null>(null)
    const [activeTab, setActiveTab] = useState(0)
    const [docTab, setDocTab] = useState(0)
    const [selectedHeaderId, setSelectedHeaderId] = useState<string | null>(null)
    const [loading, setLoading] = useState(true)
    const [actionLoading, setActionLoading] = useState<string | null>(null)

    const loadData = () => {
        return Promise.all([
            axios.get<Summary>(`${API}/analytics/summary`),
            axios.get<Match[]>(`${API}/analytics/matches`),
            axios.get<BankStatement[]>(`${API}/analytics/bank-statements`),
            axios.get<RemittanceHeader[]>(`${API}/analytics/remittance-headers`),
        ]).then(([s, m, b, r]) => {
            setSummary(s.data)
            setMatches(m.data)
            setBankStmts(b.data)
            setRemHeaders(r.data)
            if (!selectedHeaderId && r.data.length > 0) {
                setSelectedHeaderId(r.data[0].id)
            }
        })
    }

    useEffect(() => {
        loadData().finally(() => setLoading(false))
    }, [])

    const handleMarkMatched = async (id: string) => {
        setActionLoading(id)
        try {
            await axios.post(`${API}/analytics/matches/${id}/mark-matched`)
            await loadData()
        } finally {
            setActionLoading(null)
        }
    }

    const handleMarkUnmatched = async (id: string) => {
        setActionLoading(id)
        try {
            await axios.post(`${API}/analytics/matches/${id}/mark-unmatched`)
            await loadData()
        } finally {
            setActionLoading(null)
        }
    }

    const pieData = summary
        ? [
            { id: 0, value: summary.matched, label: 'Matched', color: '#4caf50' },
            { id: 1, value: summary.unmatched, label: 'Unmatched', color: '#f44336' },
            { id: 2, value: summary.manual_review, label: 'Manual Review', color: '#ff9800' },
        ]
        : []

    const filteredMatches = matchFilter
        ? matches.filter((m) => {
            if (matchFilter === 'matched') return ['AUTO_MATCHED', 'APPROVED', 'CLOSED'].includes(m.status)
            if (matchFilter === 'unmatched') return m.status === 'UNMATCHED'
            if (matchFilter === 'manual_review') return ['MANUAL_REVIEW', 'PARTIAL_MATCH', 'REJECTED'].includes(m.status)
            return true
        })
        : matches

    const matchColumns = useMemo<GridColDef[]>(() => [
        {
            field: 'status',
            headerName: 'Status',
            width: 150,
            renderCell: (params: GridRenderCellParams) => (
                <Chip size='small' label={String(params.value)} color={STATUS_COLORS[String(params.value)] ?? 'default'} />
            ),
        },
        { field: 'match_rule', headerName: 'Rule', minWidth: 180, flex: 1 },
        {
            field: 'confidence_score',
            headerName: 'Confidence',
            width: 120,
            valueGetter: (_value, row) => `${(row.confidence_score * 100).toFixed(1)}%`,
        },
        { field: 'bank_booking_date', headerName: 'Bank Date', width: 120, valueGetter: (_v, r) => r.bank_booking_date ?? '–' },
        {
            field: 'bank_amount',
            headerName: 'Bank Amount',
            width: 130,
            valueGetter: (_v, r) => fmt(r.bank_amount, r.bank_currency),
        },
        { field: 'bank_counterparty', headerName: 'Counterparty', width: 180, valueGetter: (_v, r) => r.bank_counterparty ?? '–' },
        { field: 'bank_reference', headerName: 'Bank Ref', width: 160, valueGetter: (_v, r) => r.bank_reference ?? '–' },
        { field: 'remittance_invoice_number', headerName: 'Invoice #', width: 130, valueGetter: (_v, r) => r.remittance_invoice_number ?? '–' },
        {
            field: 'remittance_paid_amount',
            headerName: 'Rem. Amount',
            width: 130,
            valueGetter: (_v, r) => fmt(r.remittance_paid_amount, r.remittance_currency),
        },
        { field: 'variance_amount', headerName: 'Variance', width: 120, valueGetter: (_v, r) => fmt(r.variance_amount) },
        {
            field: 'actions',
            headerName: 'Actions',
            width: 180,
            sortable: false,
            filterable: false,
            renderCell: (params: GridRenderCellParams<Match>) => (
                <Box display='flex' gap={0.5}>
                    <Button
                        size='small'
                        variant='outlined'
                        color='success'
                        disabled={actionLoading === params.row.id || params.row.status === 'APPROVED'}
                        onClick={() => handleMarkMatched(params.row.id)}
                    >
                        {actionLoading === params.row.id ? <CircularProgress size={14} /> : 'Match'}
                    </Button>
                    <Button
                        size='small'
                        variant='outlined'
                        color='error'
                        disabled={actionLoading === params.row.id || params.row.status === 'UNMATCHED'}
                        onClick={() => handleMarkUnmatched(params.row.id)}
                    >
                        Unmatch
                    </Button>
                </Box>
            ),
        },
    ], [actionLoading])

    const bankColumns = useMemo<GridColDef[]>(() => [
        { field: 'line_number', headerName: '#', width: 80 },
        { field: 'booking_date', headerName: 'Booking Date', width: 130 },
        { field: 'value_date', headerName: 'Value Date', width: 130, valueGetter: (_v, r) => r.value_date ?? '–' },
        { field: 'amount', headerName: 'Amount', width: 120, valueGetter: (_v, r) => fmt(r.amount) },
        { field: 'currency', headerName: 'Ccy', width: 90 },
        { field: 'counterparty_name', headerName: 'Counterparty', width: 180, valueGetter: (_v, r) => r.counterparty_name ?? '–' },
        { field: 'bank_reference', headerName: 'Bank Ref', width: 160, valueGetter: (_v, r) => r.bank_reference ?? '–' },
        { field: 'customer_reference', headerName: 'Customer Ref', width: 160, valueGetter: (_v, r) => r.customer_reference ?? '–' },
        { field: 'payment_purpose', headerName: 'Purpose', minWidth: 220, flex: 1, valueGetter: (_v, r) => r.payment_purpose ?? '–' },
    ], [])

    const remHeaderColumns = useMemo<GridColDef[]>(() => [
        { field: 'advice_number', headerName: 'Advice #', width: 150, valueGetter: (_v, r) => r.advice_number ?? '–' },
        { field: 'advice_date', headerName: 'Date', width: 130, valueGetter: (_v, r) => r.advice_date ?? '–' },
        { field: 'payer_name', headerName: 'Payer', minWidth: 180, flex: 1, valueGetter: (_v, r) => r.payer_name ?? '–' },
        {
            field: 'total_paid_amount',
            headerName: 'Total Paid',
            width: 140,
            valueGetter: (_v, r) => fmt(r.total_paid_amount, r.document_currency),
        },
        {
            field: 'line_count',
            headerName: 'Lines',
            width: 90,
            valueGetter: (_v, r) => Array.isArray(r.lines) ? r.lines.length : 0,
        },
    ], [])

    const remLineColumns = useMemo<GridColDef[]>(() => [
        { field: 'line_number', headerName: '#', width: 80 },
        { field: 'invoice_number', headerName: 'Invoice', width: 130, valueGetter: (_v, r) => r.invoice_number ?? '–' },
        { field: 'invoice_date', headerName: 'Invoice Date', width: 130, valueGetter: (_v, r) => r.invoice_date ?? '–' },
        { field: 'paid_amount', headerName: 'Paid Amount', width: 130, valueGetter: (_v, r) => fmt(r.paid_amount) },
        { field: 'currency', headerName: 'Ccy', width: 90, valueGetter: (_v, r) => r.currency ?? '–' },
        { field: 'customer_reference', headerName: 'Customer Ref', width: 150, valueGetter: (_v, r) => r.customer_reference ?? '–' },
        { field: 'raw_line_text', headerName: 'Raw Text', minWidth: 260, flex: 1 },
    ], [])

    const selectedHeader = remHeaders.find((h) => h.id === selectedHeaderId) ?? null
    const remLineRows = selectedHeader?.lines ?? []

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
                Reconciliation Analytics
            </Typography>

            <Paper sx={{ mb: 2 }}>
                <Tabs value={activeTab} onChange={(_e, v) => setActiveTab(v)}>
                    <Tab label='Reconciliation Analytics' />
                    <Tab label='Reconciliation Matches' />
                    <Tab label='Documents' />
                </Tabs>
            </Paper>

            {activeTab === 0 && (
                <Grid container spacing={3} sx={{ mb: 3 }}>
                    <Grid size={{ xs: 12, md: 6 }}>
                        <Card>
                            <CardContent>
                                <Typography variant='h6' gutterBottom>
                                    Overall Match Status
                                </Typography>
                                {summary && summary.total > 0 ? (
                                    <PieChart
                                        series={[
                                            {
                                                data: pieData,
                                                highlightScope: { fade: 'global', highlight: 'item' },
                                                innerRadius: 40,
                                            },
                                        ]}
                                        onItemClick={(_e, item) => {
                                            const keys = ['matched', 'unmatched', 'manual_review']
                                            const clicked = keys[item.dataIndex]
                                            setMatchFilter((prev) => (prev === clicked ? null : clicked))
                                        }}
                                        height={280}
                                        slotProps={{ legend: { direction: 'horizontal', position: { vertical: 'bottom', horizontal: 'center' } } }}
                                    />
                                ) : (
                                    <Typography color='text.secondary'>No match data yet.</Typography>
                                )}
                                {matchFilter && (
                                    <Typography variant='caption' color='primary'>
                                        Showing <strong>{matchFilter.replace('_', ' ')}</strong> matches below
                                    </Typography>
                                )}
                            </CardContent>
                        </Card>
                    </Grid>

                    <Grid size={{ xs: 12, md: 6 }}>
                        <Typography variant='h6' gutterBottom>
                            Tenant Breakdown
                        </Typography>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                            {summary?.tenants.map((t) => (
                                <Card key={t.id} variant='outlined'>
                                    <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
                                        <Box display='flex' justifyContent='space-between' alignItems='center'>
                                            <Box>
                                                <Typography variant='subtitle1'>{t.name}</Typography>
                                                <Typography variant='caption' color='text.secondary'>
                                                    {t.code} · {t.is_active ? 'Active' : 'Inactive'}
                                                </Typography>
                                            </Box>
                                            <Box display='flex' gap={1}>
                                                <Chip size='small' label={`✓ ${t.matched}`} color='success' variant='outlined' />
                                                <Chip size='small' label={`✗ ${t.unmatched}`} color='error' variant='outlined' />
                                                <Chip size='small' label={`~ ${t.manual_review}`} color='warning' variant='outlined' />
                                            </Box>
                                        </Box>
                                    </CardContent>
                                </Card>
                            ))}
                            {!summary?.tenants.length && (
                                <Typography color='text.secondary'>No tenants found.</Typography>
                            )}
                        </Box>
                    </Grid>
                </Grid>
            )}

            {activeTab === 1 && (
                <>
                    <Typography variant='h6' gutterBottom>
                        Reconciliation Matches {matchFilter ? `(${matchFilter.replace('_', ' ')})` : '(all)'}
                    </Typography>
                    <DataGrid
                        rows={filteredMatches}
                        columns={matchColumns}
                        autoHeight
                        disableRowSelectionOnClick
                        pageSizeOptions={[10, 25, 50]}
                        initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
                    />
                </>
            )}

            {activeTab === 2 && (
                <Paper sx={{ p: 1 }}>
                    <Tabs value={docTab} onChange={(_e, v) => setDocTab(v)} sx={{ mb: 1 }}>
                        <Tab label='Bank Statement' />
                        <Tab label='Remittance Advice' />
                    </Tabs>

                    {docTab === 0 && (
                        <DataGrid
                            rows={bankStmts}
                            columns={bankColumns}
                            autoHeight
                            disableRowSelectionOnClick
                            pageSizeOptions={[10, 25, 50]}
                            initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
                        />
                    )}

                    {docTab === 1 && (
                        <>
                            <Typography variant='subtitle1' sx={{ px: 1, py: 0.5 }}>
                                Headers
                            </Typography>
                            <DataGrid
                                rows={remHeaders}
                                columns={remHeaderColumns}
                                autoHeight
                                disableRowSelectionOnClick
                                onRowClick={(params) => setSelectedHeaderId(String(params.id))}
                                pageSizeOptions={[5, 10]}
                                initialState={{ pagination: { paginationModel: { pageSize: 5 } } }}
                                sx={{ mb: 2 }}
                            />

                            <Typography variant='subtitle1' sx={{ px: 1, py: 0.5 }}>
                                Lines {selectedHeader ? `for Advice ${selectedHeader.advice_number ?? '–'}` : ''}
                            </Typography>
                            <DataGrid
                                rows={remLineRows}
                                columns={remLineColumns}
                                autoHeight
                                disableRowSelectionOnClick
                                pageSizeOptions={[10, 25]}
                                initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
                            />
                        </>
                    )}
                </Paper>
            )}
        </Box>
    )
}
