<template>
  <div class="reports">
    <div class="page-header">
      <h2>{{ t('reports.title') }}</h2>
      <p>{{ t('reports.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('reports.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="quarterlyData.length === 0 && monthlyData.length === 0" class="loading">
      {{ t('common.noData') }}
    </div>
    <div v-else>
      <!-- Quarterly Performance -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.quarterly.title') }}</h3>
        </div>
        <div class="table-container">
          <table class="reports-table">
            <thead>
              <tr>
                <th>{{ t('reports.quarterly.quarter') }}</th>
                <th>{{ t('reports.quarterly.totalOrders') }}</th>
                <th>{{ t('reports.quarterly.totalRevenue') }}</th>
                <th>{{ t('reports.quarterly.avgOrderValue') }}</th>
                <th>{{ t('reports.quarterly.fulfillmentRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in quarterlyData" :key="q.quarter">
                <td>
                  <strong>{{ q.quarter }}</strong>
                </td>
                <td>{{ q.total_orders }}</td>
                <td>{{ formatMoney(q.total_revenue) }}</td>
                <td>{{ formatMoney(q.avg_order_value) }}</td>
                <td>
                  <span :class="getFulfillmentClass(q.fulfillment_rate)"> {{ q.fulfillment_rate }}% </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Monthly Trends Chart -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.monthlyTrend.title') }}</h3>
        </div>
        <div class="chart-container">
          <div v-if="monthlyRows.length === 0" class="loading">
            {{ t('common.noData') }}
          </div>
          <div v-else class="chart-layout">
            <div class="y-axis" aria-hidden="true">
              <span v-for="tick in yTicks" :key="tick.value" class="y-tick" :style="{ bottom: tick.offset + 'px' }">{{
                tick.label
              }}</span>
            </div>
            <div class="chart-plot">
              <div class="gridlines" aria-hidden="true">
                <div
                  v-for="tick in yTicks"
                  :key="tick.value"
                  class="gridline"
                  :style="{ bottom: tick.offset + 'px' }"
                ></div>
              </div>
              <ul class="bar-chart" role="list" :aria-label="t('reports.monthlyTrend.title')">
                <li
                  v-for="row in monthlyRows"
                  :key="row.month"
                  class="bar-wrapper"
                  role="listitem"
                  :aria-label="row.label + ': ' + formatMoney(row.revenue)"
                >
                  <div class="bar-container">
                    <div
                      class="bar"
                      :style="{ height: row.barHeight + 'px' }"
                      :title="row.label + ': ' + formatMoney(row.revenue)"
                    ></div>
                  </div>
                  <div class="bar-label" aria-hidden="true">
                    {{ row.label }}
                  </div>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <!-- Month-over-Month Comparison -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.monthOverMonth.title') }}</h3>
        </div>
        <div class="table-container">
          <table class="reports-table">
            <thead>
              <tr>
                <th>{{ t('reports.monthOverMonth.month') }}</th>
                <th>{{ t('reports.monthOverMonth.orders') }}</th>
                <th>{{ t('reports.monthOverMonth.revenue') }}</th>
                <th>{{ t('reports.monthOverMonth.change') }}</th>
                <th>{{ t('reports.monthOverMonth.growthRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in monthlyRows" :key="row.month">
                <td>
                  <strong>{{ row.label }}</strong>
                </td>
                <td>{{ row.order_count }}</td>
                <td>{{ formatMoney(row.revenue) }}</td>
                <td>
                  <span v-if="row.change !== null" :class="getChangeClass(row.change)">
                    {{ formatChange(row.change) }}
                  </span>
                  <span v-else>-</span>
                </td>
                <td>
                  <span v-if="row.change !== null" :class="getChangeClass(row.change)">
                    {{ row.growthRate }}
                  </span>
                  <span v-else>-</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Summary Stats -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.summary.totalRevenue') }}</div>
          <div class="stat-value">{{ formatMoney(totalRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">
            {{ t('reports.summary.avgMonthlyRevenue') }}
          </div>
          <div class="stat-value">{{ formatMoney(avgMonthlyRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.summary.totalOrders') }}</div>
          <div class="stat-value">{{ totalOrders }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.summary.bestQuarter') }}</div>
          <div class="stat-value">{{ bestQuarter }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import { formatCurrencyWithDecimals, convertAmount } from '../utils/currency'

const MONTH_KEYS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
const CHART_MAX_HEIGHT = 200

export default {
  name: 'Reports',
  setup() {
    const { t, currentCurrency } = useI18n()
    const { selectedPeriod, selectedLocation, selectedCategory, selectedStatus, getCurrentFilters } = useFilters()

    const loading = ref(true)
    const error = ref(null)
    const quarterlyData = ref([])
    const monthlyData = ref([])

    // Guards against an older, slower response overwriting a newer one
    let latestRequest = 0

    const loadData = async () => {
      const requestId = ++latestRequest
      try {
        loading.value = true
        error.value = null
        const filters = getCurrentFilters()
        const [quarterly, monthly] = await Promise.all([
          api.getQuarterlyReports(filters),
          api.getMonthlyTrends(filters)
        ])
        if (requestId !== latestRequest) return
        quarterlyData.value = quarterly
        monthlyData.value = monthly
      } catch (err) {
        if (requestId !== latestRequest) return
        console.error('Failed to load reports:', err)
        error.value = t('reports.loadError', { message: err.message })
      } finally {
        if (requestId === latestRequest) loading.value = false
      }
    }

    watch([selectedPeriod, selectedLocation, selectedCategory, selectedStatus], loadData)
    onMounted(loadData)

    // Formatting
    const formatMoney = (amount) => formatCurrencyWithDecimals(amount, currentCurrency.value, 2)

    const formatMonth = (monthStr) => {
      const [year, month] = monthStr.split('-')
      const key = MONTH_KEYS[parseInt(month, 10) - 1]
      return key ? `${t('months.' + key)} ${year}` : monthStr
    }

    const formatChange = (change) => {
      if (change === 0) return formatMoney(0)
      return (change > 0 ? '+' : '-') + formatMoney(Math.abs(change))
    }

    const formatGrowthRate = (current, previous) => {
      if (previous === 0) return 'N/A'
      const rate = ((current - previous) / previous) * 100
      return (rate > 0 ? '+' : '') + rate.toFixed(1) + '%'
    }

    // Derived data
    const maxRevenue = computed(() => monthlyData.value.reduce((max, m) => Math.max(max, m.revenue), 0))

    // Round the chart ceiling up to a "nice" value so the four y-axis intervals fall on
    // readable numbers without leaving much empty space above the tallest bar.
    const axisMax = computed(() => {
      if (maxRevenue.value <= 0) return 0
      const magnitude = Math.pow(10, Math.floor(Math.log10(maxRevenue.value)))
      const step = [1, 1.2, 1.6, 2, 2.4, 3, 4, 5, 6, 8, 10].find((s) => s * magnitude >= maxRevenue.value)
      return step * magnitude
    })

    const formatCompactMoney = (amount) => {
      const isYen = currentCurrency.value === 'JPY'
      return new Intl.NumberFormat(isYen ? 'ja-JP' : 'en-US', {
        style: 'currency',
        currency: isYen ? 'JPY' : 'USD',
        notation: 'compact',
        maximumFractionDigits: 1
      }).format(convertAmount(amount, currentCurrency.value))
    }

    const yTicks = computed(() => {
      if (axisMax.value === 0) return []
      return [0, 0.25, 0.5, 0.75, 1].map((fraction) => ({
        value: fraction * axisMax.value,
        label: formatCompactMoney(fraction * axisMax.value),
        offset: fraction * CHART_MAX_HEIGHT
      }))
    })

    const monthlyRows = computed(() =>
      monthlyData.value.map((m, index) => {
        const previous = index > 0 ? monthlyData.value[index - 1] : null
        return {
          ...m,
          label: formatMonth(m.month),
          barHeight: axisMax.value === 0 ? 0 : (m.revenue / axisMax.value) * CHART_MAX_HEIGHT,
          change: previous ? m.revenue - previous.revenue : null,
          growthRate: previous ? formatGrowthRate(m.revenue, previous.revenue) : null
        }
      })
    )

    const totalRevenue = computed(() => monthlyData.value.reduce((sum, m) => sum + m.revenue, 0))

    const avgMonthlyRevenue = computed(() =>
      monthlyData.value.length > 0 ? totalRevenue.value / monthlyData.value.length : 0
    )

    const totalOrders = computed(() => monthlyData.value.reduce((sum, m) => sum + m.order_count, 0))

    const bestQuarter = computed(() => {
      let best = null
      for (const q of quarterlyData.value) {
        if (!best || q.total_revenue > best.total_revenue) best = q
      }
      return best ? best.quarter : '-'
    })

    const getFulfillmentClass = (rate) => {
      if (rate >= 90) return 'badge success'
      if (rate >= 75) return 'badge warning'
      return 'badge danger'
    }

    const getChangeClass = (change) => {
      if (change > 0) return 'positive-change'
      if (change < 0) return 'negative-change'
      return ''
    }

    return {
      t,
      loading,
      error,
      quarterlyData,
      monthlyData,
      monthlyRows,
      yTicks,
      totalRevenue,
      avgMonthlyRevenue,
      totalOrders,
      bestQuarter,
      formatMoney,
      formatChange,
      getFulfillmentClass,
      getChangeClass
    }
  }
}
</script>

<style scoped>
.reports {
  padding: 0;
}

.card {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.card-header {
  margin-bottom: 1.5rem;
}

.card-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
}

.reports-table {
  width: 100%;
  border-collapse: collapse;
}

.reports-table th {
  background: #f8fafc;
  padding: 0.75rem;
  text-align: left;
  font-weight: 600;
  color: #64748b;
  border-bottom: 2px solid #e2e8f0;
}

.reports-table td {
  padding: 0.75rem;
  border-bottom: 1px solid #e2e8f0;
}

.reports-table tr:hover {
  background: #f8fafc;
}

.chart-container {
  padding: 2rem 1rem;
  min-height: 300px;
}

.chart-layout {
  display: flex;
  gap: 0.75rem;
}

.y-axis {
  position: relative;
  height: 200px;
  width: 4.5rem;
  flex-shrink: 0;
  font-size: 0.75rem;
  color: #64748b;
}

.y-tick {
  position: absolute;
  right: 0;
  transform: translateY(50%);
  white-space: nowrap;
}

.chart-plot {
  position: relative;
  flex: 1;
  min-width: 0;
}

.gridlines {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 200px;
  pointer-events: none;
}

.gridline {
  position: absolute;
  left: 0;
  right: 0;
  border-top: 1px solid #e2e8f0;
}

.bar-chart {
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  height: 250px;
  gap: 0.5rem;
  list-style: none;
  padding: 0;
  margin: 0;
}

.bar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  max-width: 80px;
}

.bar-container {
  height: 200px;
  display: flex;
  align-items: flex-end;
  width: 100%;
}

.bar {
  width: 100%;
  background: linear-gradient(to top, #3b82f6, #60a5fa);
  border-radius: 4px 4px 0 0;
  transition: all 0.3s;
}

.bar:hover {
  background: linear-gradient(to top, #2563eb, #3b82f6);
}

.bar-label {
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: #64748b;
  text-align: center;
  transform: rotate(-45deg);
  white-space: nowrap;
  margin-top: 1.5rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-top: 1.5rem;
}

@media (max-width: 1100px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border-left: 4px solid #3b82f6;
}

.stat-label {
  font-size: 0.875rem;
  color: #64748b;
  margin-bottom: 0.5rem;
}

.stat-value {
  font-size: 1.875rem;
  font-weight: 700;
  color: #0f172a;
}

.badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.875rem;
  font-weight: 500;
}

.badge.success {
  background: #dcfce7;
  color: #166534;
}

.badge.warning {
  background: #fef3c7;
  color: #92400e;
}

.badge.danger {
  background: #fee2e2;
  color: #991b1b;
}

.positive-change {
  color: #16a34a;
  font-weight: 600;
}

.negative-change {
  color: #dc2626;
  font-weight: 600;
}

.loading {
  text-align: center;
  padding: 3rem;
  color: #64748b;
}

.error {
  background: #fee2e2;
  color: #991b1b;
  padding: 1rem;
  border-radius: 8px;
  margin: 1rem 0;
}
</style>
