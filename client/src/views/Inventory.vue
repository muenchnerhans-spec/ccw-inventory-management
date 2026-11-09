<template>
  <div class="inventory">
    <div class="page-header">
      <h2>{{ t('inventory.title') }}</h2>
      <p>{{ t('inventory.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card restock-card">
        <div class="card-header restock-header">
          <div>
            <h3 class="card-title">{{ t('inventory.restocking.title') }}</h3>
            <p class="restock-description">{{ t('inventory.restocking.description') }}</p>
          </div>
          <form class="restock-controls" @submit.prevent="calculateRestocking">
            <label class="restock-label" for="restock-budget">{{ t('inventory.restocking.budgetLabel') }}</label>
            <input
              id="restock-budget"
              v-model="restockBudget"
              type="number"
              min="0"
              step="any"
              class="restock-input"
              :placeholder="t('inventory.restocking.budgetPlaceholder')"
            />
            <button type="submit" class="restock-button" :disabled="restockLoading">
              {{ restockLoading ? t('inventory.restocking.calculating') : t('inventory.restocking.calculate') }}
            </button>
          </form>
        </div>

        <div v-if="restockValidationError" class="restock-message restock-error">{{ restockValidationError }}</div>
        <div v-else-if="restockError" class="restock-message restock-error">{{ restockError }}</div>

        <div v-if="restockResult" class="restock-result">
          <div class="restock-summary">
            <div class="restock-stat">
              <span class="restock-stat-label">{{ t('inventory.restocking.summary.budget') }}</span>
              <span class="restock-stat-value">{{ formatMoney(restockResult.budget) }}</span>
            </div>
            <div class="restock-stat">
              <span class="restock-stat-label">{{ t('inventory.restocking.summary.totalCost') }}</span>
              <span class="restock-stat-value">{{ formatMoney(restockResult.total_cost) }}</span>
            </div>
            <div class="restock-stat">
              <span class="restock-stat-label">{{ t('inventory.restocking.summary.remaining') }}</span>
              <span class="restock-stat-value">{{ formatMoney(restockResult.remaining_budget) }}</span>
            </div>
            <div class="restock-stat">
              <span class="restock-stat-label">{{ t('inventory.restocking.summary.funded') }}</span>
              <span class="restock-stat-value">{{ restockResult.full_count }}</span>
            </div>
            <div class="restock-stat">
              <span class="restock-stat-label">{{ t('inventory.restocking.summary.partial') }}</span>
              <span class="restock-stat-value">{{ restockResult.partial_count }}</span>
            </div>
            <div class="restock-stat">
              <span class="restock-stat-label">{{ t('inventory.restocking.summary.unfunded') }}</span>
              <span class="restock-stat-value">{{ restockResult.unfunded_count }}</span>
            </div>
          </div>

          <div v-if="restockResult.items.length === 0" class="restock-message">
            {{ t('inventory.restocking.noCandidates') }}
          </div>
          <div v-else class="table-container">
            <table>
              <thead>
                <tr>
                  <th>{{ t('inventory.restocking.table.priority') }}</th>
                  <th>{{ t('inventory.table.sku') }}</th>
                  <th>{{ t('inventory.table.itemName') }}</th>
                  <th>{{ t('inventory.table.warehouse') }}</th>
                  <th>{{ t('inventory.restocking.table.onHand') }}</th>
                  <th>{{ t('inventory.restocking.table.needed') }}</th>
                  <th>{{ t('inventory.restocking.table.order') }}</th>
                  <th>{{ t('inventory.restocking.table.lineCost') }}</th>
                  <th>{{ t('inventory.restocking.table.demand') }}</th>
                  <th>{{ t('inventory.restocking.table.status') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(item, idx) in restockResult.items"
                  :key="item.sku"
                  :class="{ 'restock-unfunded': item.status === 'unfunded' }"
                >
                  <td>{{ idx + 1 }}</td>
                  <td><strong>{{ item.sku }}</strong></td>
                  <td>{{ translateProductName(item.name) }}</td>
                  <td>{{ translateWarehouse(item.warehouse) }}</td>
                  <td>{{ item.quantity_on_hand }}</td>
                  <td>{{ item.needed_qty }}</td>
                  <td><strong>{{ item.recommended_qty }}</strong></td>
                  <td>{{ formatMoney(item.line_cost) }}</td>
                  <td>{{ trendLabel(item.demand_trend) }}</td>
                  <td>
                    <span :class="['badge', restockStatusClass(item.status)]">
                      {{ t('inventory.restocking.status.' + item.status) }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('inventory.stockLevels') }} ({{ filteredItems.length }} {{ t('inventory.skus') }})</h3>
          <div class="search-box">
            <svg class="search-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd" />
            </svg>
            <input
              v-model="searchQuery"
              type="text"
              :placeholder="t('inventory.searchPlaceholder')"
              class="search-input"
            />
            <button
              v-if="searchQuery"
              @click="searchQuery = ''"
              class="clear-search"
              :title="t('inventory.clearSearch')"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('inventory.table.sku') }}</th>
                <th>{{ t('inventory.table.itemName') }}</th>
                <th>{{ t('inventory.table.category') }}</th>
                <th>{{ t('inventory.table.quantityOnHand') }}</th>
                <th>{{ t('inventory.table.reorderPoint') }}</th>
                <th>{{ t('inventory.table.unitCost') }}</th>
                <th>{{ t('inventory.table.totalValue') }}</th>
                <th>{{ t('inventory.table.location') }}</th>
                <th>{{ t('inventory.table.status') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in filteredItems"
                :key="item.id"
                class="clickable-row"
                @click="showItemDetail(item)"
              >
                <td><strong>{{ item.sku }}</strong></td>
                <td>{{ translateProductName(item.name) }}</td>
                <td>{{ translateCategory(item.category) }}</td>
                <td><strong>{{ item.quantity_on_hand }}</strong></td>
                <td>{{ item.reorder_point }}</td>
                <td>{{ currencySymbol }}{{ item.unit_cost.toFixed(2) }}</td>
                <td><strong>{{ currencySymbol }}{{ (item.quantity_on_hand * item.unit_cost).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) }}</strong></td>
                <td>{{ translateWarehouse(item.location) }}</td>
                <td>
                  <span :class="['badge', getStockStatusClass(item)]">
                    {{ getStockStatus(item) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <InventoryDetailModal
      :is-open="showItemModal"
      :inventory-item="selectedItem"
      @close="showItemModal = false"
    />
  </div>
</template>

<script>
import { ref, onMounted, watch, computed } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import InventoryDetailModal from '../components/InventoryDetailModal.vue'

export default {
  name: 'Inventory',
  components: {
    InventoryDetailModal
  },
  setup() {
    const { t, currentCurrency, translateProductName, translateWarehouse } = useI18n()

    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })

    const loading = ref(true)
    const error = ref(null)
    const items = ref([])
    const searchQuery = ref('')

    // Modal state
    const showItemModal = ref(false)
    const selectedItem = ref(null)

    // Use shared filters
    const { selectedLocation, selectedCategory, getCurrentFilters } = useFilters()

    // Stock status order for sorting (using status keys)
    const STATUS_ORDER = { 'lowStock': 0, 'adequate': 1, 'inStock': 2 }

    // Get stock status key (for sorting and translation)
    const getStockStatusKey = (item) => {
      if (item.quantity_on_hand <= item.reorder_point) {
        return 'lowStock'
      } else if (item.quantity_on_hand <= item.reorder_point * 1.5) {
        return 'adequate'
      } else {
        return 'inStock'
      }
    }

    // Computed property to filter items by search query and sort by stock status
    const filteredItems = computed(() => {
      let filtered = items.value

      // Apply search filter if query exists
      if (searchQuery.value.trim()) {
        const query = searchQuery.value.toLowerCase().trim()
        filtered = filtered.filter(item =>
          item.name.toLowerCase().includes(query)
        )
      }

      // Sort by stock status: Low Stock first, then Adequate, then In Stock
      // Always create a copy to avoid mutating the original array
      return filtered.slice().sort((a, b) => {
        const statusA = getStockStatusKey(a)
        const statusB = getStockStatusKey(b)
        return STATUS_ORDER[statusA] - STATUS_ORDER[statusB]
      })
    })

    const loadInventory = async () => {
      try {
        loading.value = true
        const filters = getCurrentFilters()
        // Inventory doesn't support month/status filters, only warehouse and category
        items.value = await api.getInventory({
          warehouse: filters.warehouse,
          category: filters.category
        })
      } catch (err) {
        error.value = 'Failed to load inventory: ' + err.message
      } finally {
        loading.value = false
      }
    }

    // Budget-based restocking state (independent from the stock table)
    const restockBudget = ref('')
    const restockResult = ref(null)
    const restockLoading = ref(false)
    const restockError = ref(null)
    const restockValidationError = ref(null)
    const restockCalculated = ref(false)
    let restockRequestId = 0

    const formatMoney = (value) => {
      return currencySymbol.value + Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    }

    const restockStatusClass = (status) => {
      return { full: 'success', partial: 'warning', unfunded: 'danger' }[status] || ''
    }

    const trendLabel = (trend) => {
      return t(`inventory.restocking.trend.${trend || 'none'}`)
    }

    const parseBudget = () => {
      if (restockBudget.value === '' || restockBudget.value === null) return NaN
      const n = Number(restockBudget.value)
      return Number.isFinite(n) && n >= 0 ? n : NaN
    }

    const loadRestocking = async (budget) => {
      const requestId = ++restockRequestId
      restockLoading.value = true
      restockError.value = null
      try {
        const filters = getCurrentFilters()
        const result = await api.getRestockingRecommendations(budget, {
          warehouse: filters.warehouse,
          category: filters.category
        })
        if (requestId !== restockRequestId) return
        restockResult.value = result
      } catch (err) {
        if (requestId !== restockRequestId) return
        restockError.value = t('inventory.restocking.loadError') + err.message
      } finally {
        if (requestId === restockRequestId) {
          restockLoading.value = false
        }
      }
    }

    const calculateRestocking = async () => {
      const budget = parseBudget()
      if (Number.isNaN(budget)) {
        restockValidationError.value = t('inventory.restocking.invalidBudget')
        return
      }
      restockValidationError.value = null
      restockCalculated.value = true
      await loadRestocking(budget)
    }

    // Watch for filter changes and reload data
    watch([selectedLocation, selectedCategory], () => {
      loadInventory()
      if (restockCalculated.value) {
        const budget = parseBudget()
        if (!Number.isNaN(budget)) {
          loadRestocking(budget)
        }
      }
    })

    const getStockStatus = (item) => {
      const key = getStockStatusKey(item)
      return t(`status.${key}`)
    }

    const getStockStatusClass = (item) => {
      if (item.quantity_on_hand <= item.reorder_point) {
        return 'danger'
      } else if (item.quantity_on_hand <= item.reorder_point * 1.5) {
        return 'warning'
      } else {
        return 'success'
      }
    }

    const translateCategory = (category) => {
      const categoryMap = {
        'Circuit Boards': t('categories.circuitBoards'),
        'Sensors': t('categories.sensors'),
        'Actuators': t('categories.actuators'),
        'Controllers': t('categories.controllers'),
        'Power Supplies': t('categories.powerSupplies')
      }
      return categoryMap[category] || category
    }

    const showItemDetail = (item) => {
      selectedItem.value = item
      showItemModal.value = true
    }

    onMounted(loadInventory)

    return {
      t,
      loading,
      error,
      items,
      searchQuery,
      filteredItems,
      getStockStatus,
      getStockStatusClass,
      translateCategory,
      showItemModal,
      selectedItem,
      showItemDetail,
      currencySymbol,
      translateProductName,
      translateWarehouse,
      restockBudget,
      restockResult,
      restockLoading,
      restockError,
      restockValidationError,
      calculateRestocking,
      formatMoney,
      restockStatusClass,
      trendLabel
    }
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin-bottom: 0.25rem;
}

.page-header p {
  color: #64748b;
  font-size: 0.875rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.5rem;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.card-title {
  font-size: 1rem;
  font-weight: 600;
  color: #0f172a;
  margin: 0;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 300px;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  width: 18px;
  height: 18px;
  color: #94a3b8;
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 0.5rem 2.5rem 0.5rem 2.5rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.875rem;
  color: #0f172a;
  background: #f8fafc;
  transition: all 0.2s;
}

.search-input:focus {
  outline: none;
  border-color: #3b82f6;
  background: white;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.search-input::placeholder {
  color: #94a3b8;
}

.clear-search {
  position: absolute;
  right: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.25rem;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s;
}

.clear-search:hover {
  background: #e2e8f0;
  color: #64748b;
}

.clear-search svg {
  width: 18px;
  height: 18px;
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.error {
  color: #ef4444;
}

.restock-card {
  margin-bottom: 1.5rem;
}

.restock-description {
  margin: 0.25rem 0 0;
  color: #64748b;
  font-size: 0.875rem;
}

.restock-controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.restock-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #0f172a;
}

.restock-input {
  width: 160px;
  padding: 0.5rem 0.75rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.875rem;
  color: #0f172a;
  background: #f8fafc;
}

.restock-input:focus {
  outline: none;
  border-color: #3b82f6;
  background: white;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.restock-button {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 8px;
  background: #0f172a;
  color: white;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.restock-button:hover:not(:disabled) {
  background: #1e293b;
}

.restock-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.restock-message {
  padding: 1rem 1.5rem;
  font-size: 0.875rem;
  color: #64748b;
}

.restock-message.restock-error {
  color: #ef4444;
}

.restock-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.restock-stat {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.restock-stat-label {
  font-size: 0.75rem;
  color: #64748b;
}

.restock-stat-value {
  font-size: 1.125rem;
  font-weight: 600;
  color: #0f172a;
}

.restock-unfunded td {
  opacity: 0.6;
}

.clickable-row {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.clickable-row:hover {
  background: #eff6ff !important;
}
</style>
