import { useState, useRef } from 'react'
import { Upload, Button, Progress, Tag, Card } from 'antd'
import { CameraOutlined, FileImageOutlined, EyeOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'

interface DetectionResult {
  id: string
  crop: string
  disease: string
  confidence: number
  severity: '轻度' | '中度' | '重度'
  bbox: [number, number, number, number]
  recommendation: string
  medicine: string
  dosage: string
}

const mockResults: DetectionResult[] = [
  {
    id: '1',
    crop: '芒果',
    disease: '炭疽病',
    confidence: 97.8,
    severity: '中度',
    bbox: [120, 80, 280, 220],
    recommendation: '及时喷洒咪鲜胺或苯醚甲环唑，连续防治2-3次',
    medicine: '45%咪鲜胺水乳剂',
    dosage: '稀释1500-2000倍液',
  },
  {
    id: '2',
    crop: '芒果',
    disease: '介壳虫',
    confidence: 94.2,
    severity: '轻度',
    bbox: [320, 150, 420, 280],
    recommendation: '在若虫盛发期喷施噻嗪酮或螺虫乙酯',
    medicine: '25%噻嗪酮可湿性粉剂',
    dosage: '稀释1000-1500倍液',
  },
]

const severityColors = {
  '轻度': 'green',
  '中度': 'orange',
  '重度': 'red',
}

export default function PestDetection() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [analyzing, setAnalyzing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [results, setResults] = useState<DetectionResult[]>([])
  const [imageUrl, setImageUrl] = useState<string>('')
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const handleUpload = ({ fileList }: { fileList: UploadFile[] }) => {
    setFileList(fileList)
    if (fileList.length > 0 && fileList[0].originFileObj) {
      const url = URL.createObjectURL(fileList[0].originFileObj)
      setImageUrl(url)
    }
  }

  const startAnalysis = () => {
    if (fileList.length === 0) return
    setAnalyzing(true)
    setProgress(0)
    setResults([])

    const timer = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(timer)
          setAnalyzing(false)
          setResults(mockResults)
          return 100
        }
        return prev + 10
      })
    }, 200)
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">AI 病虫害识别</h2>
        <p className="text-gray-500 mt-1">基于轻量化CNN模型，实时识别15种热带作物的42种病虫害</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：上传与分析 */}
        <div className="lg:col-span-1 space-y-4">
          <Card title="图像上传" className="shadow-sm">
            <Upload
              listType="picture-card"
              fileList={fileList}
              onChange={handleUpload}
              beforeUpload={() => false}
              maxCount={1}
              className="w-full"
            >
              {fileList.length === 0 && (
                <div className="text-center py-8">
                  <FileImageOutlined className="text-3xl text-gray-400" />
                  <p className="mt-2 text-gray-500">点击或拖拽上传作物图像</p>
                  <p className="text-xs text-gray-400 mt-1">支持 JPG、PNG 格式</p>
                </div>
              )}
            </Upload>

            <div className="flex gap-2 mt-4">
              <Button
                type="primary"
                icon={<EyeOutlined />}
                onClick={startAnalysis}
                loading={analyzing}
                disabled={fileList.length === 0}
                block
                className="bg-green-600 hover:bg-green-700"
              >
                {analyzing ? '识别中...' : '开始识别'}
              </Button>
              <Button icon={<CameraOutlined />}>
                实时拍照
              </Button>
            </div>

            {analyzing && (
              <div className="mt-4">
                <Progress percent={progress} status="active" strokeColor="#16a34a" />
                <p className="text-sm text-gray-500 mt-2 text-center">
                  {progress < 30 ? '正在预处理图像...' :
                   progress < 60 ? '正在运行AI推理...' :
                   progress < 90 ? '正在分析结果...' : '即将完成...'}
                </p>
              </div>
            )}
          </Card>

          <Card title="识别统计" className="shadow-sm">
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">今日识别次数</span>
                <span className="font-semibold text-gray-900">1,284</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">平均准确率</span>
                <span className="font-semibold text-green-600">97.5%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">平均响应时间</span>
                <span className="font-semibold text-gray-900">156ms</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">覆盖作物种类</span>
                <span className="font-semibold text-gray-900">15种</span>
              </div>
            </div>
          </Card>
        </div>

        {/* 中间：图像显示 */}
        <div className="lg:col-span-1">
          <Card title="识别图像" className="shadow-sm h-full">
            {imageUrl ? (
              <div className="relative">
                <img
                  src={imageUrl}
                  alt="作物图像"
                  className="w-full rounded-lg"
                  style={{ maxHeight: '400px', objectFit: 'contain' }}
                />
                <canvas
                  ref={canvasRef}
                  className="absolute top-0 left-0 w-full h-full"
                />
                {results.length > 0 && (
                  <div className="absolute top-2 left-2 bg-green-600 text-white px-3 py-1 rounded-full text-sm">
                    识别完成 ✓
                  </div>
                )}
              </div>
            ) : (
              <div className="h-80 bg-gray-50 rounded-lg flex items-center justify-center border-2 border-dashed border-gray-200">
                <div className="text-center">
                  <EyeOutlined className="text-4xl text-gray-300" />
                  <p className="mt-2 text-gray-400">上传图像后将在此显示识别结果</p>
                </div>
              </div>
            )}
          </Card>
        </div>

        {/* 右侧：识别结果 */}
        <div className="lg:col-span-1">
          <Card title="识别结果" className="shadow-sm h-full">
            {results.length > 0 ? (
              <div className="space-y-4">
                {results.map((result) => (
                  <div key={result.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <h4 className="font-semibold text-gray-900">{result.disease}</h4>
                        <p className="text-sm text-gray-500">{result.crop}</p>
                      </div>
                      <Tag color={severityColors[result.severity]}>{result.severity}</Tag>
                    </div>
                    <div className="mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-600">置信度</span>
                        <Progress
                          percent={result.confidence}
                          size="small"
                          strokeColor={result.confidence > 95 ? '#16a34a' : '#f59e0b'}
                          className="flex-1"
                        />
                      </div>
                    </div>
                    <div className="bg-green-50 rounded-lg p-3 text-sm">
                      <p className="font-medium text-green-800 mb-1">防治建议：</p>
                      <p className="text-green-700">{result.recommendation}</p>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                      <div className="bg-gray-50 rounded p-2">
                        <span className="text-gray-500">推荐药剂</span>
                        <p className="font-medium text-gray-900 mt-0.5">{result.medicine}</p>
                      </div>
                      <div className="bg-gray-50 rounded p-2">
                        <span className="text-gray-500">稀释比例</span>
                        <p className="font-medium text-gray-900 mt-0.5">{result.dosage}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center">
                <div className="text-center">
                  <EyeOutlined className="text-3xl text-gray-300" />
                  <p className="mt-2 text-gray-400">识别结果将显示在这里</p>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
