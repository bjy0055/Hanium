const express = require("express");
const axios = require("axios");
const bodyParser = require("body-parser");
require('dotenv').config(); // 환경 변수 로드

const app = express();
const PORT = 3000;

app.use(bodyParser.json());
app.use(express.static("public"));

async function maskTextUsingGPT(text) {
    try {
        const response = await axios.post(
            "https://api.openai.com/v1/chat/completions",
            {
                model: "gpt-3.5-turbo",
                messages: [
                    {
                        role: "system",
                        content: "You are an anonymizer. Identify and replace personal information such as names, phone numbers, email addresses, and addresses with appropriate placeholders like [NAME], [PHONE], [EMAIL], and [ADDRESS].",
                    },
                    { role: "user", content: text },
                ],
                max_tokens: 150,
            },
            {
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
                },
            }
        );

        const anonymizedText = response.data.choices[0].message.content.trim();
        return anonymizedText;
    } catch (error) {
        console.error("Error anonymizing text:", error.response ? error.response.data : error.message);
        throw new Error("Error anonymizing text");
    }
}

// 기본 경로 추가
app.get("/", (req, res) => {
    res.sendFile(__dirname + "/public/gpt.html");
});

app.post("/anonymize", async (req, res) => {
    const text = req.body.text;

    if (!text) {
        console.error("No text provided.");
        return res.status(400).send("No text provided.");
    }

    console.log(`Received text: ${text}`);

    try {
        const maskedText = await maskTextUsingGPT(text);
        console.log(`Masked text: ${maskedText}`);
        res.json({ anonymizedText: maskedText });
    } catch (error) {
        console.error(error);
        res.status(500).send("Error anonymizing text");
    }
});

app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});
