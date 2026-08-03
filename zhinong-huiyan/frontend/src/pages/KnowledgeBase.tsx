import { useState } from 'react'
import { Card, Input, Tag, Collapse } from 'antd'
import { SearchOutlined, BookOutlined } from '@ant-design/icons'

interface PestInfo {
  id: string
  name: string
  crop: string
  category: string
  symptoms: string
  causes: string
  prevention: string[]
  treatment: string[]
  severity: '轻度' | '中度' | '重度'
  season: string[]
  images: number
}

const pestDatabase: PestInfo[] = [
  {
    id: '1',
    name: '芒果炭疽病',
    crop: '芒果',
    category: '真菌性病害',
    symptoms: '叶片出现褐色至黑褐色病斑，边缘不规则；果实出现黑色凹陷斑点，潮湿时产生粉红色粘状物。',
    causes: '由Colletotrichum gloeosporioides引起，高温高湿环境利于发病，风雨传播。',
    prevention: ['清理果园病残体', '合理修剪增强通风', '开花前喷洒保护性杀菌剂'],
    treatment: ['45%咪鲜胺水乳剂 1500倍液', '10%苯醚甲环唑水分散粒剂 2000倍液', '80%代森锰锌可湿性粉剂 600倍液'],
    severity: '重度',
    season: ['3-5月', '7-9月'],
    images: 156,
  },
  {
    id: '2',
    name: '荔枝霜疫霉病',
    crop: '荔枝',
    category: '真菌性病害',
    symptoms: '花穗和果实变褐色腐烂，潮湿时产生白色霉层，病果易脱落。',
    causes: '由Peronophythora litchii引起，花期至果实发育期最易感病，高湿环境利于发病。',
    prevention: ['清园减少病源', '疏花疏果改善通风', '花期开始定期喷药保护'],
    treatment: ['72%霜脲·锰锌可湿性粉剂 600倍液', '69%烯酰·锰锌水分散粒剂 800倍液', '25%甲霜灵可湿性粉剂 500倍液'],
    severity: '重度',
    season: ['2-4月'],
    images: 203,
  },
  {
    id: '3',
    name: '槟榔黄化病',
    crop: '槟榔',
    category: '病毒性病害',
    symptoms: '叶片逐渐变黄，从老叶开始；植株生长缓慢，结果减少，严重时整株死亡。',
    causes: '由植原体引起，通过叶蝉等媒介昆虫传播，高温干旱加重发病。',
    prevention: ['选用无病种苗', '及时清除病株', '防治叶蝉等媒介昆虫'],
    treatment: ['四环素类抗生素注射', '叶面喷施锌、镁等微量元素', '加强水肥管理'],
    severity: '重度',
    season: ['全年'],
    images: 178,
  },
  {
    id: '4',
    name: '香蕉枯萎病',
    crop: '香蕉',
    category: '真菌性病害',
    symptoms: '叶片从下向上变黄枯萎，维管束褐变；假茎基部纵裂，根系腐烂。',
    causes: '由Fusarium oxysporum f.sp. cubense引起，土壤传播，可存活多年。',
    prevention: ['种植抗病品种', '轮作与非寄主作物', '无病土育苗'],
    treatment: ['土壤消毒处理', '灌根甲霜灵或多菌灵', '严重病株连根拔除销毁'],
    severity: '重度',
    season: ['4-10月'],
    images: 134,
  },
  {
    id: '5',
    name: '芒果介壳虫',
    crop: '芒果',
    category: '虫害',
    symptoms: '叶片、枝条和果实表面有白色或褐色介壳；叶片发黄，树势衰弱，诱发煤烟病。',
    causes: '多种蚧类害虫，世代重叠，高温干燥利于繁殖，枝叶茂密通风差加重发生。',
    prevention: ['合理修剪改善通风透光', '保护瓢虫等天敌', '冬季清园'],
    treatment: ['25%噻嗪酮可湿性粉剂 1000倍液', '22.4%螺虫乙酯悬浮剂 4000倍液', '40%速扑杀乳油 1500倍液'],
    severity: '中度',
    season: ['3-8月'],
    images: 89,
  },
  {
    id: '6',
    name: '菠萝心腐病',
    crop: '菠萝',
    category: '真菌性病害',
    symptoms: '心叶褐变腐烂，有臭味；植株矮小，生长停滞，严重时整株死亡。',
    causes: '由Phytophthora nicotianae引起，高温高湿利于发病，积水田块发病重。',
    prevention: ['选排水良好地块', '高畦栽培', '避免偏施氮肥'],
    treatment: ['72%霜脲·锰锌 600倍液', '69%烯酰·锰锌 800倍液', '灌根甲霜灵锰锌'],
    severity: '中度',
    season: ['5-9月'],
    images: 76,
  },
]

const severityColors = {
  '轻度': 'green',
  '中度': 'orange',
  '重度': 'red',
}

export default function KnowledgeBase() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCrop, setSelectedCrop] = useState<string | null>(null)

  const crops = ['全部', '芒果', '荔枝', '槟榔', '香蕉', '菠萝']

  const filteredPests = pestDatabase.filter((pest) => {
    const matchesSearch = pest.name.includes(searchQuery) || pest.symptoms.includes(searchQuery)
    const matchesCrop = selectedCrop && selectedCrop !== '全部' ? pest.crop === selectedCrop : true
    return matchesSearch && matchesCrop
  })

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">病虫害知识库</h2>
        <p className="text-gray-500 mt-1">覆盖42种热带作物病虫害，提供完整识别特征与防治方案</p>
      </div>

      {/* 搜索与筛选 */}
      <Card className="shadow-sm">
        <div className="flex flex-col md:flex-row gap-4">
          <Input
            placeholder="搜索病虫害名称或症状..."
            prefix={<SearchOutlined />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1"
            size="large"
          />
        </div>
        <div className="flex gap-2 mt-4 flex-wrap">
          {crops.map((crop) => (
            <Tag
              key={crop}
              color={selectedCrop === crop || (crop === '全部' && !selectedCrop) ? 'green' : 'default'}
              className="cursor-pointer px-3 py-1 text-sm"
              onClick={() => setSelectedCrop(crop === '全部' ? null : crop)}
            >
              {crop}
            </Tag>
          ))}
        </div>
      </Card>

      {/* 统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: '病虫害总数', value: '42种', color: 'bg-blue-50 text-blue-600' },
          { label: '覆盖作物', value: '15种', color: 'bg-green-50 text-green-600' },
          { label: '图像样本', value: '12,580张', color: 'bg-purple-50 text-purple-600' },
          { label: '防治方案', value: '126个', color: 'bg-orange-50 text-orange-600' },
        ].map((stat) => (
          <Card key={stat.label} className="shadow-sm">
            <p className="text-sm text-gray-500">{stat.label}</p>
            <p className={`text-2xl font-bold mt-1 ${stat.color.split(' ')[1]}`}>{stat.value}</p>
          </Card>
        ))}
      </div>

      {/* 病虫害详情 */}
      <div className="space-y-4">
        {filteredPests.map((pest) => (
          <Card key={pest.id} className="shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
                  <BookOutlined className="text-primary-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{pest.name}</h3>
                  <div className="flex gap-2 mt-1">
                    <Tag color="blue">{pest.crop}</Tag>
                    <Tag color="purple">{pest.category}</Tag>
                    <Tag color={severityColors[pest.severity]}>{pest.severity}</Tag>
                    <Tag>{pest.images}张样本</Tag>
                  </div>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-gray-500">高发季节</p>
                <div className="flex gap-1 mt-1">
                  {pest.season.map((s) => (
                    <Tag key={s}>{s}</Tag>
                  ))}
                </div>
              </div>
            </div>

            <Collapse ghost expandIconPosition="end">
              <Collapse.Panel header={<span className="font-medium text-gray-700">识别特征</span>} key="1">
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-700 leading-relaxed">{pest.symptoms}</p>
                </div>
              </Collapse.Panel>
              <Collapse.Panel header={<span className="font-medium text-gray-700">发病原因</span>} key="2">
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-700 leading-relaxed">{pest.causes}</p>
                </div>
              </Collapse.Panel>
              <Collapse.Panel header={<span className="font-medium text-gray-700">预防措施</span>} key="3">
                <ul className="space-y-2">
                  {pest.prevention.map((item, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="w-5 h-5 bg-primary-100 text-primary-600 rounded-full flex items-center justify-center text-xs flex-shrink-0 mt-0.5">
                        {i + 1}
                      </span>
                      <span className="text-sm text-gray-700">{item}</span>
                    </li>
                  ))}
                </ul>
              </Collapse.Panel>
              <Collapse.Panel header={<span className="font-medium text-gray-700">治疗方案</span>} key="4">
                <ul className="space-y-2">
                  {pest.treatment.map((item, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="w-5 h-5 bg-green-100 text-green-600 rounded-full flex items-center justify-center text-xs flex-shrink-0 mt-0.5">
                        {i + 1}
                      </span>
                      <span className="text-sm text-gray-700">{item}</span>
                    </li>
                  ))}
                </ul>
              </Collapse.Panel>
            </Collapse>
          </Card>
        ))}
      </div>
    </div>
  )
}
