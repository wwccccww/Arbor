import { test, expect } from '@playwright/test'
import path from 'node:path'

test('demo path: import chat, bootstrap inbox, see biography tree', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('邮箱').fill('demo-a@arbor.eval')
  await page.getByLabel('密码').fill('arbor-owner')
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { level: 1, name: '工作空间' })).toBeVisible()

  await page.getByRole('button', { name: /林夏/ }).click()
  await expect(page.getByRole('heading', { level: 1, name: '林夏' })).toBeVisible()

  const samplePath = path.join(process.cwd(), 'public/demo/sample-chat.txt')
  await page.getByLabel('导入文件').setInputFiles(samplePath)
  await page.getByRole('button', { name: '导入', exact: true }).click()

  await expect(page.getByRole('button', { name: '一键写入记忆并建树' })).toBeVisible({ timeout: 30000 })
  await page.getByRole('button', { name: '一键写入记忆并建树' }).click()
  await expect(page.getByText('没有待确认的记忆')).toBeVisible({ timeout: 30000 })

  await expect(page.locator('.biography-tree').getByText('面店争吵', { exact: true })).toBeVisible({
    timeout: 15000,
  })
})
