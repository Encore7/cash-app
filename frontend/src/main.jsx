import React, { useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Alert,
  AppBar,
  Box,
  Button,
  Chip,
  Container,
  CssBaseline,
  Grid,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Toolbar,
  Typography,
} from '@mui/material'
import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
})

function statusColor(status) {
  if (status === 'POSTED') return 'success'
  if (status === 'READY_TO_POST') return 'primary'
  if (status === 'REVIEW_REQUIRED') return 'warning'
  if (status === 'FAILED') return 'error'
  return 'default'
}

function Dashboard() {
  const [tenantCode, setTenantCode] = useState('bike-team-gmbh')
  const [businessDate, setBusinessDate] = useState('2026-03-19')
  const [run, setRun] = useState(null)
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')

  const stats = useMemo(() => {
    if (!items) return null
    const total = items.matches.length
    const auto = items.matches.filter((m) => m.status === 'AUTO_MATCHED').length
    const partial = items.matches.filter((m) => m.status === 'PARTIAL_MATCH').length
    const review = items.matches.filter((m) => ['MANUAL_REVIEW', 'UNMATCHED'].includes(m.status)).length
    return { total, auto, partial, review }
  }, [items])

  async function ingest() {
    setError('')
    try {
      const runResp = await api.post('/runs/ingest', {
        tenant_code: tenantCode,
        business_date: businessDate,
      })
      setRun(runResp.data)
      const itemsResp = await api.get(`/runs/${runResp.data.run_id}/items`)
      setItems(itemsResp.data)
    } catch (e) {
      setError(e?.response?.data?.detail || e.message)
    }
  }

  return (
    <>
      <CssBaseline />
      <AppBar position="static" color="transparent" elevation={0}>
        <Toolbar>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            Cash Application Analyst Dashboard
          </Typography>
        </Toolbar>
      </AppBar>
      <Container sx={{ py: 4 }}>
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Ingestion Trigger
          </Typography>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            <TextField
              label="Tenant"
              value={tenantCode}
              onChange={(e) => setTenantCode(e.target.value)}
              fullWidth
            />
            <TextField
              label="Business Date"
              type="date"
              value={businessDate}
              onChange={(e) => setBusinessDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
            <Button variant="contained" onClick={ingest}>
              Run Ingestion
            </Button>
          </Stack>
          {error ? <Alert sx={{ mt: 2 }} severity="error">{error}</Alert> : null}
        </Paper>

        {run ? (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Run Summary
            </Typography>
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography>Run ID: {run.run_id}</Typography>
              <Chip label={run.status} color={statusColor(run.status)} />
              <Typography>Parsed: {run.parsed_line_count}</Typography>
              <Typography>Matched: {run.matched_line_count}</Typography>
              <Typography>Review Required: {run.review_required_count}</Typography>
            </Stack>
          </Paper>
        ) : null}

        {stats ? (
          <Grid container spacing={2} sx={{ mb: 3 }}>
            {[
              ['Total Candidates', stats.total],
              ['Auto', stats.auto],
              ['Partial', stats.partial],
              ['Need Review', stats.review],
            ].map(([label, value]) => (
              <Grid item xs={6} md={3} key={label}>
                <Paper sx={{ p: 2 }}>
                  <Typography variant="overline">{label}</Typography>
                  <Typography variant="h4">{value}</Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>
        ) : null}

        {items ? (
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Match Candidates
            </Typography>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Status</TableCell>
                  <TableCell>Rule</TableCell>
                  <TableCell>Confidence</TableCell>
                  <TableCell>Applied</TableCell>
                  <TableCell>Variance</TableCell>
                  <TableCell>Source</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.matches.map((match) => (
                  <TableRow key={match.match_id}>
                    <TableCell>{match.status}</TableCell>
                    <TableCell>{match.match_rule}</TableCell>
                    <TableCell>{match.confidence_score}</TableCell>
                    <TableCell>{match.amount_applied || '-'}</TableCell>
                    <TableCell>{match.variance_amount || '-'}</TableCell>
                    <TableCell>{match.source}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        ) : null}
      </Container>
    </>
  )
}

createRoot(document.getElementById('root')).render(<Dashboard />)
