-- Thai keywords (and "spark"/"искр" for electrical) for the built-in services of organizations
-- seeded before they were added to ai_intake.DEFAULT_RULES. Only appends keywords a service doesn't
-- already have, so manual edits in the catalog are kept.
WITH additions(code, keyword) AS (
    VALUES
        ('emergency', 'ไฟไหม้'), ('emergency', 'ควัน'), ('emergency', 'แก๊ส'), ('emergency', 'น้ำท่วม'),
        ('plumbing', 'รั่ว'), ('plumbing', 'ท่อ'), ('plumbing', 'ชักโครก'), ('plumbing', 'ส้วม'),
        ('plumbing', 'ก๊อก'), ('plumbing', 'อ่างล้าง'), ('plumbing', 'น้ำไม่ไหล'),
        ('electrical', 'spark'), ('electrical', 'искр'), ('electrical', 'ไฟฟ้า'), ('electrical', 'ไฟดับ'),
        ('electrical', 'ไฟไม่ติด'), ('electrical', 'ปลั๊ก'), ('electrical', 'สวิตช์'), ('electrical', 'หลอดไฟ'),
        ('electrical', 'ไฟช็อต'),
        ('hvac', 'แอร์'), ('hvac', 'เครื่องปรับอากาศ'), ('hvac', 'ไม่เย็น'),
        ('appliance', 'ตู้เย็น'), ('appliance', 'เครื่องซักผ้า'), ('appliance', 'เตาอบ'), ('appliance', 'ไมโครเวฟ'),
        ('appliance', 'เครื่องทำน้ำอุ่น'),
        ('access', 'กุญแจ'), ('access', 'ประตู'), ('access', 'ล็อค'), ('access', 'ล็อก'), ('access', 'คีย์การ์ด')
),
missing AS (
    SELECT s.id, array_agg(a.keyword ORDER BY a.keyword) AS keywords
    FROM services s
    JOIN additions a ON a.code = s.code
    WHERE NOT (a.keyword = ANY(s.keywords))
    GROUP BY s.id
)
UPDATE services s
SET keywords = s.keywords || missing.keywords
FROM missing
WHERE s.id = missing.id;
