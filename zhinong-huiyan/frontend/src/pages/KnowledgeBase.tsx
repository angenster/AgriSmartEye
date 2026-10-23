import { useEffect, useMemo, useState } from 'react'
import { Alert, Card, Collapse, Empty, Input, Spin, Tag, message } from 'antd'
import { BookOutlined, SearchOutlined } from '@ant-design/icons'
import { fetchKnowledgeChunks } from '../api/endpoints'
import { describeError } from '../api/client'
import type { KnowledgeChunk } from '../api/types'

const SOURCE_LABEL: Record<string, { text: string; color: string }> = {
  ai_draft_unreviewed: { text: 'AI 草稿·待校对', color: 'orange' },
  pest_info: { text: '知识库录入', color: 'green' },
}

/** 把 chunk 文本里"症状：/成因：/预防：/防治："分段展示 */
function splitSections(text: string) {
  const sections: { label: string; body: string }[] = []
  for (const line of text.split('\n')) {
    const idx = line.indexOf('：')
    if (idx > 0) {
      sections.push({ label: line.slice(0, idx), body: line.slice(idx + 1) })
    }
  }
  return sections
}

export default function KnowledgeBase() {
  const [chunks, setChunks] = useState<KnowledgeChunk[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchKnowledgeChunks(search || undefined, undefined, 100)
      .then((data) => { if (!cancelled) setChunks(data) })
      .catch((e) => message.error(describeError(e)))
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [search])

  const unreviewed = useMemo(
    () => chunks.filter((c) => c.source === 'ai_draft_unreviewed').length,
    [chunks],
  )

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">知识库</h2>
        <p className="text-gray-500 mt-1">
          检索索引中的农技条目，即诊断 Agent 查证时使用的同一份知识源
        </p>
      </div>

      {unreviewed > 0 && (
        <Alert
          type="warning"
          showIcon
          message={`当前 ${unreviewed} 条为未经人工校对的 AI 草稿`}
          description="这些条目只含症状、成因与非化学防治措施，不含药剂名称与剂量。正式使用前需由植保专业人员对照权威资料校对。"
        />
      )}

      <Card>
        <Input
          allowClear
          size="large"
          prefix={<SearchOutlined />}
          placeholder="搜索病害名、症状或作物"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-md"
        />
      </Card>

      <Spin spinning={loading}>
        {chunks.length === 0 ? (
          <Card><Empty description={search ? '没有匹配的条目' : '索引为空，请先运行 python -m rag.indexer'} /></Card>
        ) : (
          <Card>
            <Collapse
              accordion
              items={chunks.map((c) => {
                const src = SOURCE_LABEL[c.source] ?? { text: c.source, color: 'default' }
                return {
                  key: c.id,
                  label: (
                    <div className="flex items-center gap-2 flex-wrap">
                      <BookOutlined className="text-primary-600" />
                      <span className="font-medium">{c.title}</span>
                      {c.metadata?.category && <Tag>{c.metadata.category}</Tag>}
                      <Tag color={src.color}>{src.text}</Tag>
                      <span className="text-xs text-gray-400">#{c.id}</span>
                    </div>
                  ),
                  children: (
                    <div className="space-y-2">
                      {splitSections(c.text).map((s, i) => (
                        <div key={i}>
                          <span className="text-sm font-medium text-gray-700">{s.label}：</span>
                          <span className="text-sm text-gray-600">{s.body}</span>
                        </div>
                      ))}
                    </div>
                  ),
                }
              })}
            />
          </Card>
        )}
      </Spin>
    </div>
  )
}
