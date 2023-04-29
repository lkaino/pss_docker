<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="2.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:fo="http://www.w3.org/1999/XSL/Format">
    <xsl:output method="xml" omit-xml-declaration="no" indent="yes"/>
    <xsl:strip-space elements="*"/>

   <xsl:template match="@* | node()">
        <xsl:copy>
            <xsl:apply-templates select="@* | node()"/>
        </xsl:copy>
    </xsl:template>

    <xsl:template match="Items">
        <ItemBonusStats>
        <xsl:for-each select=".//Item">
            <xsl:value-of select="./@BonusEnhancementType"/>
            <xsl:if test="position() != last()" >,</xsl:if>
        </xsl:for-each>
        </ItemBonusStats>
        <ItemBonusVals>
        <xsl:for-each select=".//Item">
            <xsl:value-of select="./@BonusEnhancementValue"/>
            <xsl:if test="position() != last()" >,</xsl:if>
        </xsl:for-each>
        </ItemBonusVals>
        <ItemDesignIDs>
        <xsl:for-each select=".//Item">
            <xsl:value-of select="./@ItemDesignId"/>
            <xsl:if test="position() != last()" >,</xsl:if>
        </xsl:for-each>
        </ItemDesignIDs>
    </xsl:template>
</xsl:stylesheet>