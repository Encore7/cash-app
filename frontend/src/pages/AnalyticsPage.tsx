import React, { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import {
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Collapse,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    Grid,
    IconButton,
    Paper,
    Stack,
    Tab,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Tabs,
    Tooltip,
    Typography,
} from '@mui/material'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp'
import DownloadIcon from '@mui/icons-material/Download'
import FindInPageIcon from '@mui/icons-material/FindInPage'
import { DataGrid, GridColDef, GridFilterModel, GridRenderCellParams, GridRowSelectionModel } from '@mui/x-data-grid'
import { PieChart } from '@mui/x-charts/PieChart'

const API = 'http://localhost:8000'

interface BuyerSummary {
    buyer_name: string | null
    remittance_doc_count: number
}

interface Summary {
    matched: number
    unmatched: number
    manual_review: number
    total: number
    buyers: BuyerSummary[]
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
    remittance_buyer_reference: string | null
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
    buyer_reference: string | null
    buyer_account_number: string | null
}

interface RemittanceLine {
    id: string
    line_number: number
    invoice_number: string | null
    invoice_date: string | null
    paid_amount: number | null
    currency: string | null
    buyer_reference: string | null
}

interface RemittanceHeader {
    id: string
    buyer_reference: string | null
    bank_reference: string | null
    buyer_account_number: string | null
    advice_date: string | null
    buyer_name: string | null
    currency: string | null
    total_paid_amount: number | null
    lines: RemittanceLine[]
}

// ---------------------------------------------------------------------------
// Evidence dialog types
// ---------------------------------------------------------------------------

interface EvidenceMatchMeta {
    id: string
    status: string
    confidence_score: number
    match_rule: string
    amount_applied: number | null
    variance_amount: number | null
    source: string
    is_selected: boolean
    notes: string | null
    reviewed_by: string | null
    reviewed_at: string | null
    review_comment: string | null
}

interface EvidenceBankStatement {
    id: string
    blob_object_id: string
    line_number: number
    booking_date: string
    value_date: string | null
    amount: number
    currency: string
    counterparty_name: string | null
    payment_purpose: string | null
    bank_reference: string | null
    buyer_reference: string | null
    buyer_account_number: string | null
    source_file_name: string | null
}

interface EvidenceRemittanceLine {
    id: string
    line_number: number
    invoice_number: string | null
    invoice_date: string | null
    paid_amount: number | null
    currency: string | null
    buyer_reference: string | null
}

interface EvidenceRemittanceHeader {
    id: string
    blob_object_id: string
    buyer_reference: string | null
    bank_reference: string | null
    buyer_account_number: string | null
    advice_date: string | null
    buyer_name: string | null
    currency: string | null
    total_paid_amount: number | null
    source_file_name: string | null
}

interface EvidenceData {
    match: EvidenceMatchMeta
    bank_statement: EvidenceBankStatement | null
    remittance_line: EvidenceRemittanceLine | null
    remittance_header: EvidenceRemittanceHeader | null
}

// ---------------------------------------------------------------------------
// EvidenceDialog component
// ---------------------------------------------------------------------------

function FieldRow({
    label,
    value,
    highlight,
}: {
    label: string
    value: React.ReactNode
    highlight?: boolean
}) {
    return (
        <Box
            display='flex'
            alignItems='flex-start'
            sx={{
                py: 0.6,
                px: 1,
                borderRadius: 1,
                bgcolor: highlight ? 'success.50' : 'transparent',
                border: highlight ? '1px solid' : '1px solid transparent',
                borderColor: highlight ? 'success.200' : 'transparent',
            }}
        >
            <Typography
                variant='caption'
                color='text.secondary'
                sx={{ width: 148, flexShrink: 0, pt: 0.1 }}
            >
                {label}
            </Typography>
            <Typography
                variant='body2'
                fontWeight={highlight ? 600 : 400}
                color={highlight ? 'success.dark' : 'text.primary'}
                sx={{ wordBreak: 'break-word' }}
            >
                {value ?? '–'}
            </Typography>
        </Box>
    )
}

function normRef(v: string | null | undefined) {
    return (v ?? '').trim().toLowerCase()
}

function refsMatch(a: string | null | undefined, b: string | null | undefined) {
    const na = normRef(a)
    const nb = normRef(b)
    return na.length > 0 && nb.length > 0 && na === nb
}

interface EvidenceDialogProps {
    matchId: string | null
    open: boolean
    onClose: () => void
}

function EvidenceDialog({ matchId, open, onClose }: EvidenceDialogProps) {
    const [data, setData] = useState<EvidenceData | null>(null)
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        if (!open || !matchId) { setData(null); return }
        setLoading(true)
        axios
            .get<EvidenceData>(`${API}/analytics/matches/${matchId}/evidence`)
            .then((r) => setData(r.data))
            .catch(() => setData(null))
            .finally(() => setLoading(false))
    }, [open, matchId])

    function handleDownload(blobId: string) {
        window.open(`${API}/analytics/blobs/${blobId}/download`, '_blank')
    }

    const bs = data?.bank_statement
    const ral = data?.remittance_line
    const rah = data?.remittance_header
    const match = data?.match

    return (
        <Dialog open={open} onClose={onClose} maxWidth='lg' fullWidth scroll='paper'>
            <DialogTitle sx={{ pb: 1 }}>
                <Box display='flex' alignItems='center' gap={1} flexWrap='wrap'>
                    <Typography variant='h6' component='span'>
                        Match Evidence
                    </Typography>
                    {match && (
                        <>
                            <Chip size='small' label={match.match_rule} variant='outlined' />
                            <Chip
                                size='small'
                                label={`${(match.confidence_score * 100).toFixed(1)}% confidence`}
                                color='primary'
                                variant='outlined'
                            />
                            <Chip
                                size='small'
                                label={match.status}
                                color={STATUS_COLORS[match.status] ?? 'default'}
                            />
                            {match.variance_amount != null && match.variance_amount !== 0 && (
                                <Chip
                                    size='small'
                                    label={`Variance: ${fmt(match.variance_amount)}`}
                                    color='warning'
                                    variant='outlined'
                                />
                            )}
                        </>
                    )}
                </Box>
            </DialogTitle>

            <DialogContent dividers>
                {loading ? (
                    <Box display='flex' justifyContent='center' py={5}>
                        <CircularProgress />
                    </Box>
                ) : data ? (
                    <Grid container spacing={2}>
                        {/* ── Remittance Advice ─────────────────────── */}
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Paper
                                variant='outlined'
                                sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}
                            >
                                <Typography variant='subtitle1' fontWeight={700} mb={1}>
                                    Remittance Advice
                                </Typography>

                                {rah ? (
                                    <>
                                        <Typography
                                            variant='overline'
                                            color='text.secondary'
                                            display='block'
                                            mb={0.5}
                                        >
                                            Header
                                        </Typography>
                                        <Divider sx={{ mb: 1 }} />
                                        <FieldRow label='Buyer Name' value={rah.buyer_name} />
                                        <FieldRow
                                            label='Buyer Reference'
                                            value={rah.buyer_reference}
                                            highlight={refsMatch(rah.buyer_reference, bs?.buyer_reference)}
                                        />
                                        <FieldRow
                                            label='Bank Reference'
                                            value={rah.bank_reference}
                                            highlight={refsMatch(rah.bank_reference, bs?.bank_reference)}
                                        />
                                        <FieldRow
                                            label='Buyer Account'
                                            value={rah.buyer_account_number}
                                            highlight={refsMatch(
                                                rah.buyer_account_number,
                                                bs?.buyer_account_number,
                                            )}
                                        />
                                        <FieldRow label='Advice Date' value={rah.advice_date} />
                                        <FieldRow
                                            label='Total Paid'
                                            value={fmt(rah.total_paid_amount, rah.currency)}
                                            highlight={
                                                rah.total_paid_amount != null &&
                                                bs != null &&
                                                Math.abs(Math.abs(rah.total_paid_amount) - Math.abs(bs.amount)) <= 0.02
                                            }
                                        />
                                    </>
                                ) : (
                                    <Typography color='text.secondary' variant='body2'>
                                        No remittance header linked.
                                    </Typography>
                                )}

                                {ral ? (
                                    <>
                                        <Typography
                                            variant='overline'
                                            color='text.secondary'
                                            display='block'
                                            mt={2}
                                            mb={0.5}
                                        >
                                            Matched Line #{ral.line_number}
                                        </Typography>
                                        <Divider sx={{ mb: 1 }} />
                                        <FieldRow label='Invoice Number' value={ral.invoice_number} />
                                        <FieldRow label='Invoice Date' value={ral.invoice_date} />
                                        <FieldRow
                                            label='Paid Amount'
                                            value={fmt(ral.paid_amount, ral.currency)}
                                        />
                                        <FieldRow label='Currency' value={ral.currency} />
                                        <FieldRow
                                            label='Buyer Reference'
                                            value={ral.buyer_reference}
                                            highlight={refsMatch(ral.buyer_reference, bs?.buyer_reference)}
                                        />
                                    </>
                                ) : (
                                    <Box mt={2}>
                                        <Typography color='text.secondary' variant='body2'>
                                            No remittance line matched.
                                        </Typography>
                                    </Box>
                                )}

                                <Box mt='auto' pt={2}>
                                    {rah ? (
                                        <Button
                                            size='small'
                                            variant='outlined'
                                            startIcon={<DownloadIcon />}
                                            onClick={() => handleDownload(rah.blob_object_id)}
                                        >
                                            Download{rah.source_file_name ? `: ${rah.source_file_name}` : ' Remittance'}
                                        </Button>
                                    ) : (
                                        <Button size='small' variant='outlined' startIcon={<DownloadIcon />} disabled>
                                            No document
                                        </Button>
                                    )}
                                </Box>
                            </Paper>
                        </Grid>

                        {/* ── Bank Statement ────────────────────────── */}
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Paper
                                variant='outlined'
                                sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}
                            >
                                <Typography variant='subtitle1' fontWeight={700} mb={1}>
                                    Bank Statement
                                </Typography>

                                {bs ? (
                                    <>
                                        <Typography
                                            variant='overline'
                                            color='text.secondary'
                                            display='block'
                                            mb={0.5}
                                        >
                                            Line #{bs.line_number}
                                        </Typography>
                                        <Divider sx={{ mb: 1 }} />
                                        <FieldRow label='Booking Date' value={bs.booking_date} />
                                        <FieldRow label='Value Date' value={bs.value_date} />
                                        <FieldRow
                                            label='Amount'
                                            value={fmt(bs.amount, bs.currency)}
                                            highlight={
                                                bs.amount != null &&
                                                rah != null &&
                                                rah.total_paid_amount != null &&
                                                Math.abs(Math.abs(bs.amount) - Math.abs(rah.total_paid_amount)) <= 0.02
                                            }
                                        />
                                        <FieldRow label='Currency' value={bs.currency} />
                                        <FieldRow
                                            label='Counterparty'
                                            value={bs.counterparty_name}
                                        />
                                        <FieldRow
                                            label='Bank Reference'
                                            value={bs.bank_reference}
                                            highlight={refsMatch(rah?.bank_reference, bs.bank_reference)}
                                        />
                                        <FieldRow
                                            label='Buyer Reference'
                                            value={bs.buyer_reference}
                                            highlight={
                                                refsMatch(rah?.buyer_reference, bs.buyer_reference) ||
                                                refsMatch(ral?.buyer_reference, bs.buyer_reference)
                                            }
                                        />
                                        <FieldRow
                                            label='Buyer Account'
                                            value={bs.buyer_account_number}
                                            highlight={refsMatch(
                                                rah?.buyer_account_number,
                                                bs.buyer_account_number,
                                            )}
                                        />
                                        <FieldRow
                                            label='Payment Purpose'
                                            value={bs.payment_purpose}
                                        />
                                    </>
                                ) : (
                                    <Typography color='text.secondary' variant='body2'>
                                        No bank statement data.
                                    </Typography>
                                )}

                                <Box mt='auto' pt={2}>
                                    {bs ? (
                                        <Button
                                            size='small'
                                            variant='outlined'
                                            startIcon={<DownloadIcon />}
                                            onClick={() => handleDownload(bs.blob_object_id)}
                                        >
                                            Download{bs.source_file_name ? `: ${bs.source_file_name}` : ' Bank Statement'}
                                        </Button>
                                    ) : (
                                        <Button size='small' variant='outlined' startIcon={<DownloadIcon />} disabled>
                                            No document
                                        </Button>
                                    )}
                                </Box>
                            </Paper>
                        </Grid>
                    </Grid>
                ) : (
                    <Typography color='text.secondary' py={3} textAlign='center'>
                        No evidence data available.
                    </Typography>
                )}
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    )
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

function statusGroup(status: string): string {
    if (['AUTO_MATCHED', 'APPROVED', 'CLOSED'].includes(status)) return 'matched'
    if (status === 'UNMATCHED') return 'unmatched'
    return 'manual_review'
}

export default function AnalyticsPage() {
    const [summary, setSummary] = useState<Summary | null>(null)
    const [matches, setMatches] = useState<Match[]>([])
    const [bankStmts, setBankStmts] = useState<BankStatement[]>([])
    const [remHeaders, setRemHeaders] = useState<RemittanceHeader[]>([])

    const [activeTab, setActiveTab] = useState(0)
    const [docTab, setDocTab] = useState(0)
    const [matchFilterGroup, setMatchFilterGroup] = useState<string | null>(null)
    const [selectedBuyerName, setSelectedBuyerName] = useState<string | null>(null)
    const [matchFilterModel, setMatchFilterModel] = useState<GridFilterModel>({ items: [] })
    const [expandedHeaderId, setExpandedHeaderId] = useState<string | null>(null)

    const [loading, setLoading] = useState(true)
    const [actionLoading, setActionLoading] = useState<string | null>(null)
    const [bulkActionLoading, setBulkActionLoading] = useState(false)
    const [selectedMatchIds, setSelectedMatchIds] = useState<GridRowSelectionModel>({ type: 'include', ids: new Set() })
    const [evidenceOpen, setEvidenceOpen] = useState(false)
    const [evidenceMatchId, setEvidenceMatchId] = useState<string | null>(null)

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

    const handleBulkMatch = async () => {
        setBulkActionLoading(true)
        try {
            const ids = Array.from(selectedMatchIds.ids).map(String)
            await axios.post(`${API}/analytics/matches/bulk-match`, { ids })
            setSelectedMatchIds({ type: 'include', ids: new Set() })
            await loadData()
        } finally {
            setBulkActionLoading(false)
        }
    }

    const handleBulkUnmatch = async () => {
        setBulkActionLoading(true)
        try {
            const ids = Array.from(selectedMatchIds.ids).map(String)
            await axios.post(`${API}/analytics/matches/bulk-unmatch`, { ids })
            setSelectedMatchIds({ type: 'include', ids: new Set() })
            await loadData()
        } finally {
            setBulkActionLoading(false)
        }
    }

    const pieData = summary
        ? [
            { id: 0, value: summary.matched, label: 'Matched', color: '#4caf50' },
            { id: 1, value: summary.unmatched, label: 'Unmatched', color: '#f44336' },
            { id: 2, value: summary.manual_review, label: 'Manual Review', color: '#ff9800' },
        ]
        : []

    function applyMatchGridFilter(group: string | null) {
        const items: GridFilterModel['items'] = []

        if (group) {
            items.push({
                id: 1,
                field: 'status_group',
                operator: 'equals',
                value: group,
            })
        }

        setMatchFilterModel({ items })
    }

    function onPieSliceClick(sliceIndex: number) {
        const keys = ['matched', 'unmatched', 'manual_review']
        const clicked = keys[sliceIndex] ?? null
        const next = matchFilterGroup === clicked ? null : clicked
        setMatchFilterGroup(next)
        setActiveTab(2)
        applyMatchGridFilter(next)
    }

    function clearMatchFilters() {
        setMatchFilterGroup(null)
        setSelectedBuyerName(null)
        setMatchFilterModel({ items: [] })
    }

    const matchRows = useMemo(
        () => matches.map((m) => ({ ...m, id: m.id, status_group: statusGroup(m.status) })),
        [matches],
    )

    const matchColumns = useMemo<GridColDef[]>(() => [
        {
            field: 'status',
            headerName: 'Status',
            width: 150,
            renderCell: (params: GridRenderCellParams) => (
                <Chip size='small' label={String(params.value)} color={STATUS_COLORS[String(params.value)] ?? 'default'} />
            ),
        },
        {
            field: 'status_group',
            headerName: 'Status Group',
            width: 130,
            hideable: true,
        },
        { field: 'match_rule', headerName: 'Rule', minWidth: 180, flex: 1 },
        {
            field: 'confidence_score',
            headerName: 'Confidence',
            width: 120,
            type: 'number',
            valueGetter: (_value, row) => row.confidence_score * 100,
            valueFormatter: (value: number | null) => value != null ? `${value.toFixed(1)}%` : '–',
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
            field: 'evidence',
            headerName: 'Evidence',
            width: 70,
            sortable: false,
            filterable: false,
            renderCell: (params: GridRenderCellParams<Match>) => (
                <Tooltip title='View match evidence'>
                    <IconButton
                        size='small'
                        color='info'
                        onClick={() => {
                            setEvidenceMatchId(params.row.id)
                            setEvidenceOpen(true)
                        }}
                    >
                        <FindInPageIcon fontSize='small' />
                    </IconButton>
                </Tooltip>
            ),
        },
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
        { field: 'buyer_reference', headerName: 'Buyer Ref', width: 160, valueGetter: (_v, r) => r.buyer_reference ?? '–' },
        { field: 'buyer_account_number', headerName: 'Acct #', width: 140, valueGetter: (_v, r) => r.buyer_account_number ?? '–' },
        { field: 'payment_purpose', headerName: 'Purpose', minWidth: 220, flex: 1, valueGetter: (_v, r) => r.payment_purpose ?? '–' },
    ], [])

    const remLineColumns = useMemo<GridColDef[]>(() => [
        { field: 'line_number', headerName: '#', width: 70 },
        { field: 'invoice_number', headerName: 'Invoice', width: 130, valueGetter: (_v, r) => r.invoice_number ?? '–' },
        { field: 'invoice_date', headerName: 'Invoice Date', width: 120, valueGetter: (_v, r) => r.invoice_date ?? '–' },
        { field: 'paid_amount', headerName: 'Paid Amount', width: 130, valueGetter: (_v, r) => fmt(r.paid_amount) },
        { field: 'currency', headerName: 'Ccy', width: 80, valueGetter: (_v, r) => r.currency ?? '–' },
        { field: 'buyer_reference', headerName: 'Buyer Ref', width: 150, valueGetter: (_v, r) => r.buyer_reference ?? '–' },
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
                Reconciliation Analytics
            </Typography>

            <Paper sx={{ mb: 2 }}>
                <Tabs value={activeTab} onChange={(_e, v) => setActiveTab(v)}>
                    <Tab label='Source Documents' />
                    <Tab label='Reconciliation Analytics' />
                    <Tab label='Reconciliation Matches' />
                </Tabs>
            </Paper>

            {activeTab === 1 && (
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
                                                arcLabel: (item) => `${item.value}`,
                                                arcLabelMinAngle: 20,
                                            },
                                        ]}
                                        onItemClick={(_e, item) => onPieSliceClick(item.dataIndex)}
                                        height={280}
                                        slotProps={{ legend: { direction: 'horizontal', position: { vertical: 'bottom', horizontal: 'center' } } }}
                                        sx={{
                                            '& .MuiChartsArcLabel-root': {
                                                fill: '#fff',
                                                fontWeight: 700,
                                                fontSize: 13,
                                            },
                                        }}
                                    />
                                ) : (
                                    <Typography color='text.secondary'>No match data yet.</Typography>
                                )}
                            </CardContent>
                        </Card>
                    </Grid>

                    <Grid size={{ xs: 12, md: 6 }}>
                        <Typography variant='h6' gutterBottom>
                            Buyer Activity
                        </Typography>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                            {summary?.buyers.map((b) => (
                                <Card
                                    key={b.buyer_name ?? '__unknown__'}
                                    variant={selectedBuyerName === b.buyer_name ? 'elevation' : 'outlined'}
                                >
                                    <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
                                        <Box display='flex' justifyContent='space-between' alignItems='center'>
                                            <Typography variant='subtitle1'>
                                                {b.buyer_name ?? 'Unknown Buyer'}
                                            </Typography>
                                            <Chip
                                                size='small'
                                                label={`${b.remittance_doc_count} doc${b.remittance_doc_count !== 1 ? 's' : ''}`}
                                                color='primary'
                                                variant='outlined'
                                            />
                                        </Box>
                                    </CardContent>
                                </Card>
                            ))}
                            {!summary?.buyers.length && (
                                <Typography color='text.secondary'>No buyer data found.</Typography>
                            )}
                        </Box>
                    </Grid>
                </Grid>
            )}

            {activeTab === 2 && (
                <>
                    <Stack direction='row' justifyContent='space-between' alignItems='center' mb={1}>
                        <Typography variant='h6'>Reconciliation Matches</Typography>
                        <Stack direction='row' gap={1}>
                            <Button
                                variant='contained'
                                color='success'
                                size='small'
                                disabled={selectedMatchIds.ids.size === 0 || bulkActionLoading}
                                onClick={handleBulkMatch}
                            >
                                {bulkActionLoading ? <CircularProgress size={14} /> : `Bulk Match (${selectedMatchIds.ids.size})`}
                            </Button>
                            <Button
                                variant='contained'
                                color='error'
                                size='small'
                                disabled={selectedMatchIds.ids.size === 0 || bulkActionLoading}
                                onClick={handleBulkUnmatch}
                            >
                                {bulkActionLoading ? <CircularProgress size={14} /> : `Bulk Unmatch (${selectedMatchIds.ids.size})`}
                            </Button>
                            <Button onClick={clearMatchFilters}>Clear Filters</Button>
                        </Stack>
                    </Stack>

                    <DataGrid
                        rows={matchRows}
                        columns={matchColumns}
                        autoHeight
                        checkboxSelection
                        pageSizeOptions={[10, 20, 50]}
                        initialState={{
                            pagination: { paginationModel: { pageSize: 20 } },
                            columns: {
                                columnVisibilityModel: {
                                    status_group: false,
                                },
                            },
                        }}
                        filterModel={matchFilterModel}
                        onFilterModelChange={setMatchFilterModel}
                        rowSelectionModel={selectedMatchIds}
                        onRowSelectionModelChange={setSelectedMatchIds}
                    />
                </>
            )}

            {activeTab === 0 && (
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
                            pageSizeOptions={[10, 20, 50]}
                            initialState={{
                                pagination: { paginationModel: { pageSize: 20 } },
                                sorting: { sortModel: [{ field: 'line_number', sort: 'asc' }] },
                            }}
                        />
                    )}

                    {docTab === 1 && (
                        <TableContainer>
                            <Table size='small'>
                                <TableHead>
                                    <TableRow sx={{ bgcolor: 'action.hover' }}>
                                        <TableCell sx={{ width: 48, p: 0.5 }} />
                                        <TableCell>Buyer Ref</TableCell>
                                        <TableCell>Date</TableCell>
                                        <TableCell>Buyer</TableCell>
                                        <TableCell>Total Paid</TableCell>
                                        <TableCell sx={{ width: 70 }}>Lines</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {remHeaders.map((hdr) => {
                                        const isOpen = expandedHeaderId === hdr.id
                                        const lineRows = (hdr.lines ?? []).map((ln) => ({ ...ln, id: ln.id }))
                                        return (
                                            <React.Fragment key={hdr.id}>
                                                <TableRow hover>
                                                    <TableCell sx={{ p: 0.5 }}>
                                                        <IconButton
                                                            size='small'
                                                            onClick={() => setExpandedHeaderId((prev) => prev === hdr.id ? null : hdr.id)}
                                                        >
                                                            {isOpen
                                                                ? <KeyboardArrowUpIcon fontSize='small' />
                                                                : <KeyboardArrowDownIcon fontSize='small' />}
                                                        </IconButton>
                                                    </TableCell>
                                                    <TableCell>{hdr.buyer_reference ?? '–'}</TableCell>
                                                    <TableCell>{hdr.advice_date ?? '–'}</TableCell>
                                                    <TableCell>{hdr.buyer_name ?? '–'}</TableCell>
                                                    <TableCell>{fmt(hdr.total_paid_amount, hdr.currency)}</TableCell>
                                                    <TableCell>{Array.isArray(hdr.lines) ? hdr.lines.length : 0}</TableCell>
                                                </TableRow>
                                                <TableRow>
                                                    <TableCell colSpan={6} sx={{ p: 0, border: 0 }}>
                                                        <Collapse in={isOpen} unmountOnExit>
                                                            <Box sx={{ p: 1.5, bgcolor: 'action.hover' }}>
                                                                <DataGrid
                                                                    rows={lineRows}
                                                                    columns={remLineColumns}
                                                                    autoHeight
                                                                    disableRowSelectionOnClick
                                                                    hideFooter
                                                                    density='compact'
                                                                    sx={{
                                                                        border: '1px solid',
                                                                        borderColor: 'divider',
                                                                        bgcolor: 'background.paper',
                                                                    }}
                                                                />
                                                            </Box>
                                                        </Collapse>
                                                    </TableCell>
                                                </TableRow>
                                            </React.Fragment>
                                        )
                                    })}
                                    {remHeaders.length === 0 && (
                                        <TableRow>
                                            <TableCell colSpan={6} align='center' sx={{ py: 3, color: 'text.secondary' }}>
                                                No remittance advice documents found.
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    )}
                </Paper>
            )}

            <EvidenceDialog
                matchId={evidenceMatchId}
                open={evidenceOpen}
                onClose={() => setEvidenceOpen(false)}
            />
        </Box>
    )
}
